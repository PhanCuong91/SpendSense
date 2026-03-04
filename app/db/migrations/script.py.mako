"""
Revision ID: ${revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = ${revision | repr}
down_revision = ${down_revision | repr}
branch_labels = ${branch_labels | repr}
depends_on = ${depends_on | repr}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass