import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    def _verify() -> bool:
        try:
            _hasher.verify(password_hash, password)
            return True
        except VerifyMismatchError:
            return False

    return await asyncio.to_thread(_verify)
