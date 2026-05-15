import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt

from app.config import settings

_private_key: str | None = None
_public_key: str | None = None

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def _get_private_key() -> str:
    global _private_key
    if _private_key is None:
        _private_key = Path(settings.JWT_PRIVATE_KEY_PATH).read_text()
    return _private_key


def _get_public_key() -> str:
    global _public_key
    if _public_key is None:
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
            load_pem_private_key,
        )
        priv = load_pem_private_key(_get_private_key().encode(), password=None)
        _public_key = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    return _public_key


def create_access_token(
    *,
    sub: str,
    username: str,
    display_name: str,
    department_id: str | None,
    department_name: str | None,
    role: str,
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub,
        "username": username,
        "display_name": display_name,
        "department_id": department_id,
        "department_name": department_name,
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_SECONDS),
    }
    return jwt.encode(claims, _get_private_key(), algorithm="RS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _get_public_key(), algorithms=["RS256"])


def generate_refresh_token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex  # 64-char hex string
