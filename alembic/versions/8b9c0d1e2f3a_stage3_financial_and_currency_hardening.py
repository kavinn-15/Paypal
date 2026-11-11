"""stage3_financial_and_currency_hardening

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b9c0d1e2f3a'
down_revision: Union[str, Sequence[str], None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Update client_predictions table to include invoice_id
    if 'client_predictions' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('client_predictions')}
        if 'invoice_id' not in existing_cols:
            with op.batch_alter_table('client_predictions', schema=None) as batch_op:
                batch_op.add_column(sa.Column('invoice_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key('fk_client_predictions_invoice_id', 'invoices', ['invoice_id'], ['id'], ondelete='CASCADE')
                batch_op.create_index('ix_client_predictions_invoice_id', ['invoice_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'client_predictions' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('client_predictions')}
        if 'invoice_id' in existing_cols:
            with op.batch_alter_table('client_predictions', schema=None) as batch_op:
                batch_op.drop_index('ix_client_predictions_invoice_id')
                batch_op.drop_constraint('fk_client_predictions_invoice_id', type_='foreignkey')
                batch_op.drop_column('invoice_id')
