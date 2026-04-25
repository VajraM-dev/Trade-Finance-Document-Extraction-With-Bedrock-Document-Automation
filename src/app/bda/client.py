from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aioboto3

from app.settings import Settings


def _session(settings: Settings) -> aioboto3.Session:
    return aioboto3.Session(
        aws_access_key_id=settings.aws_access_key_id.get_secret_value() if settings.aws_access_key_id else None,
        aws_secret_access_key=settings.aws_secret_access_key.get_secret_value() if settings.aws_secret_access_key else None,
        region_name=settings.aws_region,
    )


@asynccontextmanager
async def bda_runtime(settings: Settings) -> AsyncIterator:
    async with _session(settings).client("bedrock-data-automation-runtime") as c:
        yield c


@asynccontextmanager
async def s3(settings: Settings) -> AsyncIterator:
    async with _session(settings).client("s3") as c:
        yield c
