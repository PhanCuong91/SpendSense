"""
Revision ID: 16a1cc9c98ec
Revises: 25e3615898c8
Create Date: 2026-08-08 10:50:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '16a1cc9c98ec'
down_revision = '25e3615898c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'misa_import_state',
        sa.Column('parsed_candidate_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('imported_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('account', sa.String(), nullable=True),
        sa.Column('datetime', sa.String(), nullable=True),
        sa.Column('classification', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ['parsed_candidate_id'],
            ['parsed_transaction_candidate.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('parsed_candidate_id'),
    )


def downgrade() -> None:
    op.drop_table('misa_import_state')
