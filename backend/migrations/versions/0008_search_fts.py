"""PostgreSQL full-text search for the search module (Epic E7, FR-SRCH-1).

Generated tsvector columns + GIN indexes on resources.title,
announcements.title/body, and messages.body — the upgrade path the
search module's own repository docstring has documented since it was
built. Postgres-only (STORED generated columns); SQLite (the test suite)
keeps using ILIKE, selected at query time by dialect
(search/repository.py).

Revision ID: 0008_search_fts
Revises: 0007_recording_egress
"""

from alembic import op

revision = "0008_search_fts"
down_revision = "0007_recording_egress"
branch_labels = None
depends_on = None

_TARGETS = [
    ("resources", "to_tsvector('english', coalesce(title, ''))"),
    (
        "announcements",
        "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''))",
    ),
    ("messages", "to_tsvector('english', coalesce(body, ''))"),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite (tests/dev without Postgres) uses ILIKE instead.
    for table, expr in _TARGETS:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN search_vector tsvector "
            f"GENERATED ALWAYS AS ({expr}) STORED"
        )
        op.execute(f"CREATE INDEX ix_{table}_search_vector ON {table} USING GIN (search_vector)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, _ in _TARGETS:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_search_vector")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS search_vector")
