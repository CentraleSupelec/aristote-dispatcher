"""Default routing mode

Revision ID: c63af0f18c5d
Revises: 9cf7cf124677
Create Date: 2025-09-19 14:17:42.550210

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c63af0f18c5d"
down_revision: Union[str, Sequence[str], None] = "9cf7cf124677"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "default_routing_mode",
            sa.Enum("any", "private-first", "private-only", native_enum=False),
            nullable=False,
            server_default="any",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "default_routing_mode")
