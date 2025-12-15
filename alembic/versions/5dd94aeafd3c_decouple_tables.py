"""decouple tables

Revision ID: 5dd94aeafd3c
Revises: 8e1d058df426
Create Date: 2025-12-12 13:24:26.822013

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "5dd94aeafd3c"
down_revision: Union[str, Sequence[str], None] = "8e1d058df426"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # /!\ constraint name is custom due to historical reasons (tables were managed by hand when the table was created)
    op.drop_constraint(op.f("fk_user_name"), "metrics", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        op.f("fk_user_name"),
        "metrics",
        "users",
        ["user_name"],
        ["name"],
    )
