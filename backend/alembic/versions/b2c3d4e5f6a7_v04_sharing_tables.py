"""v0.4 sharing tables: project_shares + projects.user_id NOT NULL prep

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-31 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create project_shares table."""
    op.create_table(
        "project_shares",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("permission", sa.String(), nullable=False, server_default="viewer"),
        sa.Column("shared_by", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shared_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("project_shares", schema=None) as batch_op:
        batch_op.create_index(
            "idx_project_shares_unique",
            ["project_id", "user_id"],
            unique=True,
            sqlite_where=sa.text("revoked_at IS NULL"),
        )
        batch_op.create_index(
            "idx_project_shares_user",
            ["user_id"],
            unique=False,
            sqlite_where=sa.text("revoked_at IS NULL"),
        )


def downgrade() -> None:
    """Drop project_shares table."""
    op.drop_table("project_shares")
