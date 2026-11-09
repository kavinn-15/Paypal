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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Update actions table
    if 'actions' in existing_tables:
        existing_action_cols = {col['name'] for col in inspector.get_columns('actions')}
        action_cols = [
            ('approval_version', sa.Column('approval_version', sa.Integer(), nullable=False, server_default='1')),
            ('obligation_id', sa.Column('obligation_id', sa.Integer(), nullable=True)),
            ('payout_recipient_email', sa.Column('payout_recipient_email', sa.String(length=255), nullable=True)),
            ('approved_payload_hash', sa.Column('approved_payload_hash', sa.String(length=64), nullable=True)),
            ('approved_at', sa.Column('approved_at', sa.DateTime(), nullable=True)),
            ('is_simulated', sa.Column('is_simulated', sa.Boolean(), nullable=False, server_default=sa.text('0'))),
        ]
        missing_action_cols = [(cname, ccol) for cname, ccol in action_cols if cname not in existing_action_cols]
        existing_fks = {fk.get('name') for fk in inspector.get_foreign_keys('actions')}
        with op.batch_alter_table('actions', schema=None) as batch_op:
            for cname, ccol in missing_action_cols:
                batch_op.add_column(ccol)
            if 'fk_actions_obligation_id_obligations' not in existing_fks:
                batch_op.create_foreign_key('fk_actions_obligation_id_obligations', 'obligations', ['obligation_id'], ['id'], ondelete='SET NULL')

    # 2. Update invoices table
    if 'invoices' in existing_tables:
        existing_invoice_cols = {col['name'] for col in inspector.get_columns('invoices')}
        if 'is_simulated_paid' not in existing_invoice_cols:
            with op.batch_alter_table('invoices', schema=None) as batch_op:
                batch_op.add_column(sa.Column('is_simulated_paid', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # 3. Update obligations table
    if 'obligations' in existing_tables:
        existing_obligation_cols = {col['name'] for col in inspector.get_columns('obligations')}
        obligation_cols = [
            ('split_consent_recorded', sa.Column('split_consent_recorded', sa.Boolean(), nullable=False, server_default=sa.text('0'))),
            ('split_consent_source', sa.Column('split_consent_source', sa.String(length=100), nullable=True)),
            ('split_consent_timestamp', sa.Column('split_consent_timestamp', sa.DateTime(), nullable=True)),
            ('split_consent_is_simulated', sa.Column('split_consent_is_simulated', sa.Boolean(), nullable=False, server_default=sa.text('0'))),
        ]
        missing_obligation_cols = [(cname, ccol) for cname, ccol in obligation_cols if cname not in existing_obligation_cols]
        if missing_obligation_cols:
            with op.batch_alter_table('obligations', schema=None) as batch_op:
                for cname, ccol in missing_obligation_cols:
                    batch_op.add_column(ccol)

    # 4. Update payment_history table with robust unique-index inspection
    if 'payment_history' in existing_tables:
        existing_ph_cols = {col['name'] for col in inspector.get_columns('payment_history')}
        if 'transaction_reference' not in existing_ph_cols:
            with op.batch_alter_table('payment_history', schema=None) as batch_op:
                batch_op.add_column(sa.Column('transaction_reference', sa.String(length=255), nullable=True))

        # Inspect indexes thoroughly: verify unique attribute, not just index name
        ph_indexes = inspector.get_indexes('payment_history')
        unique_tx_indexes = [
            idx for idx in ph_indexes
            if idx.get('column_names') == ['transaction_reference'] and idx.get('unique')
        ]
        non_unique_tx_indexes = [
            idx for idx in ph_indexes
            if (idx.get('column_names') == ['transaction_reference'] or idx.get('name') == 'ix_payment_history_transaction_reference')
            and not idx.get('unique')
        ]

        # If a unique index is not yet active, or if a non-unique index exists that needs replacement:
        if not unique_tx_indexes or non_unique_tx_indexes:
            # Check for duplicate non-null transaction references before applying uniqueness
            dup_records = conn.execute(sa.text("""
                SELECT transaction_reference, COUNT(*) as cnt
                FROM payment_history
                WHERE transaction_reference IS NOT NULL
                GROUP BY transaction_reference
                HAVING COUNT(*) > 1
            """)).fetchall()

            if dup_records:
                dup_summary = ", ".join(f"'{row[0]}' ({row[1]} records)" for row in dup_records)
                raise ValueError(
                    f"Cannot apply unique index on payment_history(transaction_reference): "
                    f"found duplicate non-null transaction references: {dup_summary}. "
                    "Existing financial records have been strictly preserved. "
                    "Please resolve duplicate records before re-running migration."
                )

            with op.batch_alter_table('payment_history', schema=None) as batch_op:
                for idx in non_unique_tx_indexes:
                    batch_op.drop_index(idx['name'])
                if not unique_tx_indexes:
                    batch_op.create_index(
                        batch_op.f('ix_payment_history_transaction_reference'),
                        ['transaction_reference'],
                        unique=True
                    )


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

