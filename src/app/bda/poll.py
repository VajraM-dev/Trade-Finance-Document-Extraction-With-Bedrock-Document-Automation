import asyncio
import time
from dataclasses import dataclass

import structlog
from botocore.exceptions import ClientError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.bda.client import bda_runtime
from app.settings import Settings

log = structlog.get_logger("bda.poll")

BACKOFF_SCHEDULE = [3, 5, 8, 13, 21, 21, 21, 21, 21, 21, 21]


class TransientBdaError(Exception):
    pass


class BdaTerminalFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CompletionResult:
    output_s3_uri: str


@retry(
    retry=retry_if_exception_type(TransientBdaError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def _check_status(settings: Settings, *, invocation_arn: str) -> dict:
    async with bda_runtime(settings) as client:
        try:
            return await client.get_data_automation_status(invocationArn=invocation_arn)
        except ClientError as err:
            code = err.response.get("Error", {}).get("Code", "")
            if code in {"ThrottlingException", "ServiceUnavailable"}:
                raise TransientBdaError(str(err)) from err
            raise


async def wait_for_completion(
    settings: Settings, *, invocation_arn: str
) -> CompletionResult:
    deadline = time.monotonic() + settings.bda_poll_max_seconds
    idx = 0
    while True:
        if time.monotonic() > deadline:
            raise BdaTerminalFailure("TimeoutError", "BDA polling exceeded max wait")
        resp = await _check_status(settings, invocation_arn=invocation_arn)
        status = resp.get("status", "")
        log.debug("bda.poll.tick", invocation_arn=invocation_arn, status=status)
        if status == "Success":
            output = resp.get("outputConfiguration", {}).get("s3Uri") or resp.get("outputLocation")
            if not output:
                raise BdaTerminalFailure("MissingOutput", "BDA reported success without output URI")
            return CompletionResult(output_s3_uri=output)
        if status == "ServiceError":
            raise BdaTerminalFailure("ServiceError", resp.get("errorMessage", "BDA service error"))
        if status == "ClientError":
            raise BdaTerminalFailure("ClientError", resp.get("errorMessage", "BDA client error"))

        wait = BACKOFF_SCHEDULE[min(idx, len(BACKOFF_SCHEDULE) - 1)]
        idx += 1
        await asyncio.sleep(wait)
