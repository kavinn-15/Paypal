"""add_action_approval_and_payout_fields

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-11-09 17:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e6f7a8b9c0d'
down_revision: Union[str, Sequence[str], None] = '4d5e6f7a8b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update actions table
    with op.batch_alter_table('actions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('approval_version', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('obligation_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('payout_recipient_email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('approved_payload_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('is_simulated', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.create_foreign_key('fk_actions_obligation_id_obligations', 'obligations', ['obligation_id'], ['id'], ondelete='SET NULL')

    # 2. Update invoices table
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_simulated_paid', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # 3. Update obligations table
    with op.batch_alter_table('obligations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('split_consent_recorded', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('split_consent_source', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('split_consent_timestamp', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('split_consent_is_simulated', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # 4. Update payment_history table
    with op.batch_alter_table('payment_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('transaction_reference', sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f('ix_payment_history_transaction_reference'), ['transaction_reference'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('payment_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_history_transaction_reference'))
        batch_op.drop_column('transaction_reference')

    with op.batch_alter_table('obligations', schema=None) as batch_op:
        batch_op.drop_column('split_consent_is_simulated')
        batch_op.drop_column('split_consent_timestamp')
        batch_op.drop_column('split_consent_source')
        batch_op.drop_column('split_consent_recorded')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('is_simulated_paid')

    with op.batch_alter_table('actions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_actions_obligation_id_obligations', type_='foreignkey')
        batch_op.drop_column('is_simulated')
        batch_op.drop_column('approved_payload_hash')
        batch_op.drop_column('payout_recipient_email')
        batch_op.drop_column('obligation_id')
        batch_op.drop_column('approval_version')

