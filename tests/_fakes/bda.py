"""In-process fake replacing aioboto3 bedrock-data-automation-runtime calls.

Behavior:
- start_invocation(...) records the request and writes a deterministic result JSON
  to the moto S3 output bucket under the requested output prefix.
- wait_for_completion(...) returns the output S3 URI immediately.
- fetch_and_parse(...) reads the deterministic JSON via sync boto3 (so it works
  with moto's mock_aws, which does not intercept aiobotocore reliably) and
  delegates to the production parse_payload for shape parity.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import boto3

_FAKE = {
    "bill_of_lading": {
        "matched_blueprint": {"name": "bill_of_lading"},
        "pages": [{"page_index": 0}],
        "inference_result": {
            "bol_number": "BOL-FAKE-1",
            "shipper_name": "Acme",
            "consignee_name": "Globex",
            "containers": [{"container_number": "ABCD1234567", "seal_number": "S-1"}],
        },
        "explainability_info": {
            "bol_number": {"confidence": 0.99},
            "shipper_name": {"confidence": 0.96},
        },
    }
}


class FakeBdaState:
    def __init__(self):
        self.invocations: dict[str, dict[str, Any]] = {}


def make_fake_modules(state: FakeBdaState, output_bucket: str):
    """Returns (fake_start_invocation, fake_wait_for_completion, fake_fetch_and_parse) coroutines."""

    async def fake_start_invocation(settings, *, job_id, s3_input_uri, s3_output_prefix):
        from app.bda.invoke import InvocationStarted

        arn = f"arn:aws:bedrock:us-east-1:000000000000:data-automation-invocation/{uuid.uuid4()}"
        prefix = s3_output_prefix.removeprefix(f"s3://{output_bucket}/")
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.put_object(
            Bucket=output_bucket,
            Key=f"{prefix}custom_output.json",
            Body=json.dumps(_FAKE["bill_of_lading"]).encode("utf-8"),
        )
        state.invocations[arn] = {
            "input": s3_input_uri,
            "output_prefix": s3_output_prefix,
        }
        return InvocationStarted(invocation_arn=arn)

    async def fake_wait_for_completion(settings, *, invocation_arn):
        from app.bda.poll import CompletionResult

        rec = state.invocations.get(invocation_arn)
        if rec is None:
            raise RuntimeError("unknown invocation")
        return CompletionResult(output_s3_uri=rec["output_prefix"])

    async def fake_fetch_and_parse(settings, *, output_s3_uri):
        # moto's mock_aws does not reliably intercept aioboto3, so use sync boto3
        # to read the JSON written by fake_start_invocation, then delegate to the
        # production parser for shape parity.
        from app.bda.parse import parse_payload

        bucket, _, prefix = output_s3_uri.removeprefix("s3://").partition("/")
        s3 = boto3.client("s3", region_name="us-east-1")
        listing = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        keys = [obj["Key"] for obj in listing.get("Contents", [])]
        candidate = next(
            (k for k in keys if k.endswith("custom_output.json") or k.endswith("result.json")),
            keys[0] if keys else None,
        )
        if candidate is None:
            raise RuntimeError(f"no BDA output found at {output_s3_uri}")
        obj = s3.get_object(Bucket=bucket, Key=candidate)
        payload = json.loads(obj["Body"].read())
        return parse_payload(payload)

    return fake_start_invocation, fake_wait_for_completion, fake_fetch_and_parse
