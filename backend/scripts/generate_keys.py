#!/usr/bin/env python
"""Generate RSA-2048 key pair for JWT RS256 signing.

Usage (run from backend/):
    python scripts/generate_keys.py
"""
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

keys_dir = Path(__file__).parent.parent / "keys"
keys_dir.mkdir(exist_ok=True)

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
private_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
public_pem = private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

(keys_dir / "private.pem").write_bytes(private_pem)
(keys_dir / "public.pem").write_bytes(public_pem)
print(f"Keys written to {keys_dir.resolve()}/")
print("  private.pem  — keep secret, set JWT_PRIVATE_KEY_PATH=keys/private.pem in .env")
print("  public.pem   — can be shared for external token verification")
