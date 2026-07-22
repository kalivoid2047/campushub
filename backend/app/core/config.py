from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "info"

    # Native local installs in dev (no containers) — docs/13-deployment-guide.md §1.
    database_url: str = "postgresql+asyncpg://campushub:campushub@localhost:5432/campushub"
    redis_url: str = "redis://localhost:6379/0"

    # RS256 keypair paths (docs/08-security-design.md §2). When unset in
    # development, an ephemeral keypair is generated at process start —
    # tokens do not survive restarts, which is acceptable for local dev only.
    jwt_private_key_path: str | None = None
    jwt_public_key_path: str | None = None
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 7

    # Object storage; when unset, storage falls back to local filesystem
    # (early development convenience — docs/04-system-architecture.md §10).
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str | None = None
    local_storage_path: str = "./storage-data"

    # LiveKit SFU (docs/10-virtual-classroom.md): a self-hosted, native-install
    # server (infra/systemd/campushub-livekit.service). livekit_url is the
    # wss:// endpoint handed to Flutter clients to open the media connection;
    # the api key/secret sign short-lived room-join tokens server-side and
    # are never exposed to clients. Unset in dev disables Join (session
    # lifecycle/attendance still work without a running LiveKit server).
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None

    # CORS (docs/06-api-design.md): the Flutter web target calls this API
    # cross-origin from whatever host serves the web build. Auth is
    # Bearer-token-only (no cookies), so a wildcard is safe even with this
    # enabled — there is no session credential for a hostile origin to ride
    # on. Production deployments should still narrow this to the real
    # web-client origin(s) via CORS_ORIGINS (comma-separated).
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
