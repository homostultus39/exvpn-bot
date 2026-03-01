import base64
import os

from Crypto.Cipher import AES

from bot.management.settings import get_settings


def _get_encryption_key() -> bytes:
    key_b64 = get_settings().password_encryption_key
    if not key_b64:
        raise ValueError(
            "PASSWORD_ENCRYPTION_KEY must be set in .env. "
            "Generate with: python -c \"from Crypto.Random import get_random_bytes; import base64; print(base64.b64encode(get_random_bytes(16)).decode())\""
        )
    return base64.b64decode(key_b64)


def encrypt_password(password: str) -> bytes:
    key = _get_encryption_key()
    nonce = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(password.encode("utf-8"))
    return nonce + tag + ciphertext


def decrypt_password(encrypted_password: bytes) -> str:
    key = _get_encryption_key()
    nonce = encrypted_password[:12]
    tag = encrypted_password[12:28]
    ciphertext = encrypted_password[28:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")