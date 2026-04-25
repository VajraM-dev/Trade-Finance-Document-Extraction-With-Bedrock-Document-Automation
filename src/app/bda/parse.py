import json
from dataclasses import dataclass
from typing import Any

import structlog
from botocore.exceptions import ClientError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.bda.client import s3
from app.settings import Settings

log = structlog.get_logger("bda.parse")

KNOWN_BLUEPRINTS = {"bill_of_lading", "commercial_invoice", "packing_list"}


@dataclass(frozen=True)
class ParsedResult:
    matched_blueprint: str
    pages: int
    fields: dict[str, Any]
    confidences: dict[str, Any]
    field_count: int
    raw: dict[str, Any]


def _normalize_blueprint(name: str | None) -> str:
    if not name:
        return "unknown"
    n = name.removesuffix("_blueprint")
    return n if n in KNOWN_BLUEPRINTS else "unknown"


def _count_fields(inference: dict[str, Any]) -> int:
    n = 0
    for _, value in inference.items():
        n += 1
        if isinstance(value, list) and value and isinstance(value[0], dict):
            n += len(value[0].keys())
    return n


def _walk_confidences(node: Any) -> Any:
    if isinstance(node, dict):
        if "confidence" in node and "value" in node and not isinstance(
            node.get("value"), (dict, list)
        ):
            return float(node["confidence"])
        nested: dict[str, Any] = {}
        for k, v in node.items():
            r = _walk_confidences(v)
            if r is not None:
                nested[k] = r
        return nested or None
    if isinstance(node, list):
        results = [_walk_confidences(x) for x in node]
        results = [r for r in results if r is not None]
        return results or None
    return None


def _flatten_confidences(explainability: Any) -> dict[str, Any]:
    if isinstance(explainability, list):
        merged: dict[str, Any] = {}
        for entry in explainability:
            r = _walk_confidences(entry)
            if isinstance(r, dict):
                merged.update(r)
        return merged
    if isinstance(explainability, dict):
        r = _walk_confidences(explainability)
        return r if isinstance(r, dict) else {}
    return {}


def parse_payload(payload: dict[str, Any]) -> ParsedResult:
    name_obj = payload.get("matched_blueprint") or {}
    raw_name = name_obj.get("name") if isinstance(name_obj, dict) else None
    blueprint = _normalize_blueprint(raw_name)

    pages_list = payload.get("pages") or []
    pages = len(pages_list) if isinstance(pages_list, list) else 0

    inference = payload.get("inference_result") or {}
    if not isinstance(inference, dict):
        inference = {}

    confidences = _flatten_confidences(payload.get("explainability_info"))
    return ParsedResult(
        matched_blueprint=blueprint,
        pages=pages,
        fields=inference,
        confidences=confidences,
        field_count=_count_fields(inference),
        raw=payload,
    )


@retry(
    retry=retry_if_exception_type(ClientError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _list_objects(settings: Settings, *, bucket: str, prefix: str) -> list[str]:
    async with s3(settings) as client:
        resp = await client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", [])]


@retry(
    retry=retry_if_exception_type(ClientError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _fetch_json(settings: Settings, *, bucket: str, key: str) -> dict[str, Any]:
    async with s3(settings) as client:
        obj = await client.get_object(Bucket=bucket, Key=key)
        body = await obj["Body"].read()
    return json.loads(body)


def _split_s3_uri(uri: str) -> tuple[str, str]:
    bucket, _, key = uri.removeprefix("s3://").partition("/")
    return bucket, key


def _pick_custom_output(keys: list[str]) -> str | None:
    custom = [k for k in keys if "/custom_output/" in k and k.endswith("result.json")]
    if custom:
        return custom[0]
    fallback = [k for k in keys if k.endswith("result.json") or k.endswith("custom_output.json")]
    return fallback[0] if fallback else (keys[0] if keys else None)


def _pick_standard_output(keys: list[str]) -> str | None:
    std = [k for k in keys if "/standard_output/" in k and k.endswith("result.json")]
    return std[0] if std else None


def _extract_paths_from_job_metadata(meta: dict[str, Any]) -> tuple[str | None, str | None]:
    for asset in meta.get("output_metadata") or []:
        for seg in asset.get("segment_metadata") or []:
            return seg.get("custom_output_path"), seg.get("standard_output_path")
    return None, None


async def _resolve_output_paths(
    settings: Settings, *, output_s3_uri: str
) -> tuple[str | None, str | None]:
    """Return (custom_output_uri, standard_output_uri) given BDA's reported output URI.

    BDA returns either a direct path to job_metadata.json or a prefix containing it.
    """
    bucket, key = _split_s3_uri(output_s3_uri)
    if key.endswith("job_metadata.json"):
        meta = await _fetch_json(settings, bucket=bucket, key=key)
        return _extract_paths_from_job_metadata(meta)

    keys = await _list_objects(settings, bucket=bucket, prefix=key)
    job_meta_keys = [k for k in keys if k.endswith("job_metadata.json")]
    if job_meta_keys:
        meta = await _fetch_json(settings, bucket=bucket, key=job_meta_keys[0])
        return _extract_paths_from_job_metadata(meta)

    custom_key = _pick_custom_output(keys)
    standard_key = _pick_standard_output(keys)
    custom_uri = f"s3://{bucket}/{custom_key}" if custom_key else None
    standard_uri = f"s3://{bucket}/{standard_key}" if standard_key else None
    return custom_uri, standard_uri


async def fetch_and_parse(settings: Settings, *, output_s3_uri: str) -> ParsedResult:
    custom_uri, standard_uri = await _resolve_output_paths(
        settings, output_s3_uri=output_s3_uri
    )
    if not custom_uri:
        raise RuntimeError(f"no BDA custom_output found at {output_s3_uri}")

    bucket, key = _split_s3_uri(custom_uri)
    payload = await _fetch_json(settings, bucket=bucket, key=key)
    parsed = parse_payload(payload)

    if parsed.pages == 0 and standard_uri:
        std_bucket, std_key = _split_s3_uri(standard_uri)
        std_payload = await _fetch_json(settings, bucket=std_bucket, key=std_key)
        page_count = 0
        std_pages = std_payload.get("pages")
        if isinstance(std_pages, list):
            page_count = len(std_pages)
        else:
            md = std_payload.get("metadata") or {}
            if isinstance(md, dict):
                page_count = int(md.get("number_of_pages") or 0)
        if page_count:
            parsed = ParsedResult(
                matched_blueprint=parsed.matched_blueprint,
                pages=page_count,
                fields=parsed.fields,
                confidences=parsed.confidences,
                field_count=parsed.field_count,
                raw=parsed.raw,
            )
    return parsed
