"""Object storage abstraction (docs/04-system-architecture.md section 10).

Provider-agnostic: LocalStorageBackend for early development (no external
services required), S3StorageBackend for MinIO/S3 in staging/production.
Keys are always tenant-namespaced by callers; the backend never invents keys.
"""

import hashlib
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class StorageBackend(Protocol):
    async def save(self, key: str, data: bytes) -> None: ...

    async def read(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    def presigned_url(self, key: str, expires_seconds: int = 300) -> str | None:
        """A time-limited direct URL, or None if the backend cannot presign
        (local dev) — in which case the API streams the bytes itself."""
        ...


class LocalStorageBackend:
    """Filesystem-backed storage for development (docs/13 section 1)."""

    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        # Keys are server-generated (never user-supplied), but normalize
        # defensively against traversal anyway (docs/08 section 6).
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError("Invalid storage key")
        return path

    async def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def presigned_url(self, key: str, expires_seconds: int = 300) -> str | None:
        return None  # local backend streams through the API


class S3StorageBackend:
    """S3/MinIO-backed storage for staging/production.

    Uses boto3 presigned URLs so large downloads bypass the API
    (docs/04 section 10). Instantiated lazily to keep boto3 out of the
    dev/test import path.
    """

    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str):
        import boto3

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def save(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    async def read(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presigned_url(self, key: str, expires_seconds: int = 300) -> str | None:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        settings = get_settings()
        if settings.s3_endpoint_url and settings.s3_bucket:
            _backend = S3StorageBackend(
                endpoint_url=settings.s3_endpoint_url,
                access_key=settings.s3_access_key or "",
                secret_key=settings.s3_secret_key or "",
                bucket=settings.s3_bucket,
            )
        else:
            _backend = LocalStorageBackend(settings.local_storage_path)
    return _backend


def reset_storage_for_tests() -> None:
    global _backend
    _backend = None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
