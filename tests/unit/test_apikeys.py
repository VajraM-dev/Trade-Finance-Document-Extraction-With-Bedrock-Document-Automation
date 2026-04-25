from cryptography.fernet import Fernet

from app.services.apikeys import compute_lookup_hash, decrypt_key, encrypt_key, generate_key


def test_generate_key_length():
    k = generate_key()
    assert len(k) >= 40
    assert "=" not in k


def test_lookup_hash_is_deterministic():
    pepper = b"x" * 32
    a = compute_lookup_hash(pepper, "abc")
    b = compute_lookup_hash(pepper, "abc")
    assert a == b
    assert a != compute_lookup_hash(pepper, "different")


def test_encrypt_decrypt_round_trip():
    fkey = Fernet.generate_key()
    ct = encrypt_key(fkey, "secret-key")
    assert decrypt_key(fkey, ct) == "secret-key"
