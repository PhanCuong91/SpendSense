"""
Revision ID: 25e3615898c8
Revises:
Create Date: 2026-03-05 21:31:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '25e3615898c8'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_log table
    op.create_table('audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create email_raw table
    op.create_table('email_raw',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('gmail_message_id', sa.String(), nullable=False),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('sender', sa.String(), nullable=True),
        sa.Column('recipient', sa.String(), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('received_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('processed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gmail_message_id')
    )
    op.create_index(op.f('ix_email_raw_gmail_message_id'), 'email_raw', ['gmail_message_id'], unique=False)

    # Create event table
    op.create_table('event',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('datetime_sgt', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('sender', sa.String(), nullable=True),
        sa.Column('receiver', sa.String(), nullable=True),
        sa.Column('reference', sa.Text(), nullable=True),
        sa.Column('email_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['email_id'], ['email_raw.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create error_log table
    op.create_table('error_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['email_id'], ['email_raw.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create parsed_transaction_candidate table
    op.create_table('parsed_transaction_candidate',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('datetime_sgt', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('inferred_sender', sa.String(), nullable=True),
        sa.Column('inferred_receiver', sa.String(), nullable=True),
        sa.Column('raw_reference', sa.Text(), nullable=True),
        sa.Column('debit_credit', sa.Enum('debit', 'credit', 'spend', 'earn', name='debitcredit'), nullable=True),
        sa.Column('classification_hint', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['email_id'], ['email_raw.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email_id')
    )

    # Create correlation_link table
    op.create_table('correlation_link',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('debit_candidate_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('credit_candidate_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('correlation_type', sa.String(), nullable=False),
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['credit_candidate_id'], ['parsed_transaction_candidate.id'], ),
        sa.ForeignKeyConstraint(['debit_candidate_id'], ['parsed_transaction_candidate.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('correlation_link')
    op.drop_table('parsed_transaction_candidate')
    op.drop_table('error_log')
    op.drop_table('event')
    op.drop_index(op.f('ix_email_raw_gmail_message_id'), table_name='email_raw')
    op.drop_table('email_raw')
    op.drop_table('audit_log')