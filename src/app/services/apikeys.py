import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet


def generate_key() -> str:
    return secrets.token_urlsafe(32)


def compute_lookup_hash(pepper: bytes, key: str) -> bytes:
    return hmac.new(pepper, key.encode("utf-8"), hashlib.sha256).digest()


def encrypt_key(fernet_key: bytes, key: str) -> bytes:
    return Fernet(fernet_key).encrypt(key.encode("utf-8"))


def decrypt_key(fernet_key: bytes, ciphertext: bytes) -> str:
    return Fernet(fernet_key).decrypt(ciphertext).decode("utf-8")


def last_four(key: str) -> str:
    return key[-4:]
