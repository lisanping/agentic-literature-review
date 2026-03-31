"""v0.4 auth tables: users, refresh_tokens, audit_log

Revision ID: a1b2c3d4e5f6
Revises: 83abe7eb52df
Create Date: 2026-03-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "83abe7eb52df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users, refresh_tokens, and audit_log tables."""
    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("preferences", sqlite.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index("idx_users_email", ["email"], unique=True)
        batch_op.create_index(
            "idx_users_role",
            ["role"],
            unique=False,
            sqlite_where=sa.text("is_active = 1"),
        )

    # ── refresh_tokens ──
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.create_index("idx_refresh_tokens_user", ["user_id"], unique=False)
        batch_op.create_index(
            "idx_refresh_tokens_expires", ["expires_at"], unique=False
        )

    # ── audit_log ──
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("details", sqlite.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_index(
            "idx_audit_log_user", ["user_id", "created_at"], unique=False
        )
        batch_op.create_index(
            "idx_audit_log_action", ["action", "created_at"], unique=False
        )


def downgrade() -> None:
    """Drop v0.4 auth tables."""
    op.drop_table("audit_log")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
