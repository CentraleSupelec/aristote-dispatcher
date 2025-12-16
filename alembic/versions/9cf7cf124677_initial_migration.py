"""Initial migration

Revision ID: 9cf7cf124677
Revises:
Create Date: 2025-09-19 13:38:54.858988

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9cf7cf124677"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("client_type", sa.String(length=255), nullable=True),
        # /!\ constraint names are custom due to historical reasons (tables were managed by hand before this migration)
        sa.PrimaryKeyConstraint("id", name="users_pkey"),
        sa.UniqueConstraint("name", name="users_name_unique"),
        sa.UniqueConstraint("token", name="unique_token"),
        # /!\ due to historical reasons (tables were managed by hand before this migration)
        if_not_exists=True,
    )
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_name", sa.String(length=255), nullable=False),
        sa.Column("request_date", sa.DateTime(), nullable=True),
        sa.Column("sent_to_llm_date", sa.DateTime(), nullable=True),
        sa.Column("response_date", sa.DateTime(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("server", sa.String(length=255), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        # /!\ constraint names are custom due to historical reasons (tables were managed by hand before this migration)
        sa.ForeignKeyConstraint(["user_name"], ["users.name"], "fk_user_name"),
        sa.PrimaryKeyConstraint("id", name="metrics_pkey"),
        # /!\ due to historical reasons (tables were managed by hand before this migration)
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("metrics")
    op.drop_table("users")
