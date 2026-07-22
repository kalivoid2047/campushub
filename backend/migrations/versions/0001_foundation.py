"""Foundation schema: tenants, users, roles, structure, audit, quotas + RLS.

Implements docs/05-database-design.md sections 3.1-3.6, 3.18-3.19, and the
Row-Level Security isolation policies from section 1 / docs/08 section 1.

Revision ID: 0001_foundation
Revises: None
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None

# Tables carrying tenant_id that get an RLS isolation policy
# (docs/05-database-design.md section 6: RLS keyed on app.current_tenant).
TENANT_SCOPED_TABLES = ["users", "departments", "courses", "audit_logs"]


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.String(63), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="provisioning"),
        sa.Column(
            "storage_quota_bytes", sa.BigInteger, nullable=False, server_default=str(10 * 1024**3)
        ),
        *_timestamps(),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("offline_token_hash", sa.Text, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("permissions", sa.JSON, nullable=False, server_default="{}"),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "role_id", sa.Uuid, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("scope_department_id", sa.Uuid, nullable=True),
        sa.Column("scope_course_id", sa.Uuid, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "user_id",
            "role_id",
            "scope_department_id",
            "scope_course_id",
            name="uq_user_roles_grant",
        ),
    )
    op.create_index("ix_user_roles_user", "user_roles", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["user_id"])

    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
    )
    op.create_index("ix_departments_tenant_id", "departments", ["tenant_id"])

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "department_id",
            sa.Uuid,
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("term", sa.String(32), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "code", "term", name="uq_courses_tenant_code_term"),
    )
    op.create_index("ix_courses_tenant_id", "courses", ["tenant_id"])

    op.create_table(
        "course_enrollments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "course_id", sa.Uuid, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="student"),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        *_timestamps(),
        sa.UniqueConstraint("course_id", "user_id", name="uq_enrollments_course_user"),
    )
    op.create_index("ix_enrollments_user", "course_enrollments", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("actor_id", sa.Uuid, nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.Uuid, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])

    op.create_table(
        "storage_quotas",
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("used_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("quota_bytes", sa.BigInteger, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- Row-Level Security (PostgreSQL only) ---------------------------------
    # Defense-in-depth layer 2 (layer 1 = tenant-scoped repository queries).
    # The application sets app.current_tenant per connection/transaction.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in TENANT_SCOPED_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation_{table} ON {table} "
                f"USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
            )
        # Generic updated_at touch trigger (docs/05-database-design.md section 8).
        op.execute("""
            CREATE OR REPLACE FUNCTION trg_touch_updated_at() RETURNS trigger AS $$
            BEGIN
                NEW.updated_at = now();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """)
        for table in [
            "tenants",
            "users",
            "roles",
            "user_roles",
            "refresh_tokens",
            "departments",
            "courses",
            "course_enrollments",
        ]:
            op.execute(
                f"CREATE TRIGGER touch_updated_at_{table} BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION trg_touch_updated_at()"
            )


def downgrade() -> None:
    for table in [
        "storage_quotas",
        "audit_logs",
        "course_enrollments",
        "courses",
        "departments",
        "refresh_tokens",
        "user_roles",
        "roles",
        "users",
        "tenants",
    ]:
        op.drop_table(table)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS trg_touch_updated_at")
