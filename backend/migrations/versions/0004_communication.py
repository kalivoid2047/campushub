"""Communication: channels, channel_members, messages, announcements
(docs/05 sections 3.10-3.11).

Revision ID: 0004_communication
Revises: 0003_resources
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_communication"
down_revision = "0003_resources"
branch_labels = None
depends_on = None


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
        "channels",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column(
            "course_id", sa.Uuid, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("name", sa.String(200), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_channels_tenant_id", "channels", ["tenant_id"])
    op.create_index("ix_channels_course", "channels", ["course_id"])

    op.create_table(
        "channel_members",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "channel_id", sa.Uuid, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        *_timestamps(),
        sa.UniqueConstraint("channel_id", "user_id", name="uq_channel_members"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "channel_id", sa.Uuid, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "sender_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachments", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("client_id", sa.Uuid, nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("client_id", name="uq_messages_client_id"),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_channel_created", "messages", ["channel_id", "created_at"])

    op.create_table(
        "announcements",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("scope_id", sa.Uuid, nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "published_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        *_timestamps(),
    )
    op.create_index("ix_announcements_tenant_id", "announcements", ["tenant_id"])
    op.create_index("ix_announcements_scope", "announcements", ["scope", "scope_id"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ["channels", "messages", "announcements"]:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation_{table} ON {table} "
                f"USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
            )
        for table in ["channels", "channel_members", "messages", "announcements"]:
            op.execute(
                f"CREATE TRIGGER touch_updated_at_{table} BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION trg_touch_updated_at()"
            )


def downgrade() -> None:
    op.drop_table("announcements")
    op.drop_table("messages")
    op.drop_table("channel_members")
    op.drop_table("channels")
