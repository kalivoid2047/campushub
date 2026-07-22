"""Sync core: change log + idempotency ledger (docs/09-offline-sync.md).

Revision ID: 0002_sync_core
Revises: 0001_foundation
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_sync_core"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_changes",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid, nullable=False),
        sa.Column("entity_table", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Uuid, nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("version", sa.BigInteger, nullable=False, server_default="1"),
        sa.Column("changed_by", sa.Uuid, nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_sync_changes_tenant_id_id", "sync_changes", ["tenant_id", "id"])

    op.create_table(
        "sync_applied_ops",
        sa.Column("client_id", sa.Uuid, primary_key=True),
        sa.Column("tenant_id", sa.Uuid, nullable=False),
        sa.Column("entity_table", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Uuid, nullable=False),
        sa.Column("result", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_sync_applied_ops_tenant_id", "sync_applied_ops", ["tenant_id"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ["sync_changes", "sync_applied_ops"]:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation_{table} ON {table} "
                f"USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
            )


def downgrade() -> None:
    op.drop_table("sync_applied_ops")
    op.drop_table("sync_changes")
