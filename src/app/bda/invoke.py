from dataclasses import dataclass

import structlog
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.bda.client import bda_runtime
from app.settings import Settings

log = structlog.get_logger("bda.invoke")


class TransientBdaError(Exception):
    pass


def _is_transient(err: ClientError) -> bool:
    code = err.response.get("Error", {}).get("Code", "")
    return code in {"ThrottlingException", "ServiceUnavailable", "InternalServerException"}


@dataclass(frozen=True)
class InvocationStarted:
    invocation_arn: str


@retry(
    retry=retry_if_exception_type(TransientBdaError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def start_invocation(
    settings: Settings,
    *,
    job_id: str,
    s3_input_uri: str,
    s3_output_prefix: str,
) -> InvocationStarted:
    log.info("bda.invoke.started", job_id=job_id, input=s3_input_uri)
    async with bda_runtime(settings) as client:
        try:
            resp = await client.invoke_data_automation_async(
                inputConfiguration={"s3Uri": s3_input_uri},
                outputConfiguration={"s3Uri": s3_output_prefix},
                dataAutomationConfiguration={
                    "dataAutomationProjectArn": settings.bda_project_arn,
                    "stage": "LIVE",
                },
                dataAutomationProfileArn=settings.bda_profile_arn,
                clientToken=job_id,
            )
        except ClientError as err:
            if _is_transient(err):
                raise TransientBdaError(str(err)) from err
            log.error("bda.invoke.failed", job_id=job_id, code=err.response.get("Error", {}).get("Code"))
            raise

    arn = resp["invocationArn"]
    log.info("bda.invoke.success", job_id=job_id, invocation_arn=arn)
    return InvocationStarted(invocation_arn=arn)
