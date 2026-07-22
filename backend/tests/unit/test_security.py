"""Unit tests for password hashing and JWT primitives (docs/08 section 2)."""

import uuid

import pytest
from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert hashed.startswith("$argon2id$")
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    user_id, tenant_id = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, roles=["student"])
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["roles"] == ["student"]


def test_tampered_token_rejected():
    token = create_access_token(user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["student"])
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(HTTPException) as exc:
        decode_access_token(tampered)
    assert exc.value.status_code == 401


def test_refresh_token_only_hash_matches():
    raw, hashed = generate_refresh_token()
    assert raw != hashed
    assert hash_refresh_token(raw) == hashed
    assert len(hashed) == 64  # sha256 hex
