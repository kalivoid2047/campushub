"""Resources: modules, resources, resource_versions (docs/05 sections 3.7-3.9).

Revision ID: 0003_resources
Revises: 0002_sync_core
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_resources"
down_revision = "0002_sync_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "modules",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid,
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.Uuid,
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_modules_tenant_id", "modules", ["tenant_id"])
    op.create_index("ix_modules_course", "modules", ["course_id", "position"])

    op.create_table(
        "resources",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid,
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "module_id",
            sa.Uuid,
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("current_version_id", sa.Uuid, nullable=True),
        sa.Column("download_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_resources_tenant_id", "resources", ["tenant_id"])
    op.create_index("ix_resources_module_deleted", "resources", ["module_id", "deleted_at"])

    op.create_table(
        "resource_versions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "resource_id",
            sa.Uuid,
            sa.ForeignKey("resources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("uploaded_by", sa.Uuid, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("resource_id", "version_number", name="uq_resource_versions"),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ["modules", "resources"]:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation_{table} ON {table} "
                f"USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
            )
        for table in ["modules", "resources", "resource_versions"]:
            op.execute(
                f"CREATE TRIGGER touch_updated_at_{table} BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION trg_touch_updated_at()"
            )


def downgrade() -> None:
    op.drop_table("resource_versions")
    op.drop_table("resources")
    op.drop_table("modules")
