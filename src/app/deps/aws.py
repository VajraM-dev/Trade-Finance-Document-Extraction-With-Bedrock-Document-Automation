from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aioboto3

from app.settings import Settings


@asynccontextmanager
async def s3_client(settings: Settings) -> AsyncIterator:
    session = aioboto3.Session(
        aws_access_key_id=settings.aws_access_key_id.get_secret_value() if settings.aws_access_key_id else None,
        aws_secret_access_key=settings.aws_secret_access_key.get_secret_value() if settings.aws_secret_access_key else None,
        region_name=settings.aws_region,
    )
    async with session.client("s3") as client:
        yield client
