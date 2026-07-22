"""Password hashing, JWT issuance/verification, and RBAC dependencies.

Implements docs/08-security-design.md §2–3: Argon2id password hashing,
RS256 JWTs (15-min access / rotated refresh), tenant-scoped RBAC enforced
via FastAPI dependencies. The tenant_id in the JWT claims is the only
tenant identity the backend ever trusts — never a client-supplied value.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

_password_hasher = PasswordHasher()  # argon2id defaults per OWASP guidance
bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "RS256"


# --- Password hashing -------------------------------------------------------


def hash_password(plain: str) -> str:
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


# --- Key management ----------------------------------------------------------


@lru_cache
def _keypair() -> tuple[str, str]:
    """Returns (private_pem, public_pem).

    Loads from configured paths; in development without configured paths,
    generates an ephemeral keypair (tokens invalidated on restart — dev only).
    """
    settings = get_settings()
    if settings.jwt_private_key_path and settings.jwt_public_key_path:
        with open(settings.jwt_private_key_path) as f:
            private_pem = f.read()
        with open(settings.jwt_public_key_path) as f:
            public_pem = f.read()
        return private_pem, public_pem

    if settings.environment == "production":
        raise RuntimeError("JWT key paths must be configured in production")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


# --- Tokens ------------------------------------------------------------------


def create_access_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, roles: list[str]) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_ttl_minutes),
        "type": "access",
    }
    private_pem, _ = _keypair()
    return jwt.encode(claims, private_pem, algorithm=ALGORITHM)


def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Only the hash is persisted
    (docs/08-security-design.md §4)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    _, public_pem = _keypair()
    try:
        claims = jwt.decode(token, public_pem, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    if claims.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    return claims


# --- Request principals & RBAC ------------------------------------------------


class CurrentUser:
    def __init__(self, user_id: uuid.UUID, tenant_id: uuid.UUID, roles: list[str]) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.roles = roles

    def has_any_role(self, *names: str) -> bool:
        return bool(set(self.roles) & set(names))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    claims = decode_access_token(credentials.credentials)
    return CurrentUser(
        user_id=uuid.UUID(claims["sub"]),
        tenant_id=uuid.UUID(claims["tenant_id"]),
        roles=list(claims.get("roles", [])),
    )


def require_role(*allowed_roles: str):
    """Dependency factory enforcing RBAC (docs/08-security-design.md §3).

    Object-level tenant/ownership checks remain the responsibility of the
    service/repository layers — this guard is layer one of two.
    """

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_any_role(*allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return user

    return _check
