from app.deps.aws import s3_client
from app.settings import Settings


async def presigned_get_url(settings: Settings, *, bucket: str, key: str, ttl: int | None = None) -> str:
    expires = ttl if ttl is not None else settings.presigned_url_ttl_seconds
    async with s3_client(settings) as s3:
        return await s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires
        )


async def upload_stream(
    settings: Settings, *, bucket: str, key: str, body, content_type: str
) -> None:
    async with s3_client(settings) as s3:
        await s3.upload_fileobj(body, bucket, key, ExtraArgs={"ContentType": content_type})
