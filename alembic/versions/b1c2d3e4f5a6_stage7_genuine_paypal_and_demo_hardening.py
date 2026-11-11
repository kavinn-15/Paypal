"""stage7_genuine_paypal_and_demo_hardening

Revision ID: b1c2d3e4f5a6
Revises: 9c0d1e2f3a4b
Create Date: 2026-11-11 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '9c0d1e2f3a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Update invoices table
    if 'invoices' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('invoices')}
        with op.batch_alter_table('invoices', schema=None) as batch_op:
            if 'is_seeded' not in existing_cols:
                batch_op.add_column(sa.Column('is_seeded', sa.Boolean(), server_default=sa.false(), nullable=False))
            if 'invoice_number' not in existing_cols:
                batch_op.add_column(sa.Column('invoice_number', sa.String(100), nullable=True))
            if 'provider_status' not in existing_cols:
                batch_op.add_column(sa.Column('provider_status', sa.String(50), nullable=True))

    # 2. Update obligations table
    if 'obligations' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('obligations')}
        with op.batch_alter_table('obligations', schema=None) as batch_op:
            if 'is_demo' not in existing_cols:
                batch_op.add_column(sa.Column('is_demo', sa.Boolean(), server_default=sa.false(), nullable=False))

    # 3. Update rescue_plans table
    if 'rescue_plans' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('rescue_plans')}
        with op.batch_alter_table('rescue_plans', schema=None) as batch_op:
            if 'is_demo' not in existing_cols:
                batch_op.add_column(sa.Column('is_demo', sa.Boolean(), server_default=sa.false(), nullable=False))

    # 4. Update actions table
    if 'actions' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('actions')}
        with op.batch_alter_table('actions', schema=None) as batch_op:
            if 'provider_request_id' not in existing_cols:
                batch_op.add_column(sa.Column('provider_request_id', sa.String(255), nullable=True))
            if 'execution_error' not in existing_cols:
                batch_op.add_column(sa.Column('execution_error', sa.Text(), nullable=True))
            if 'is_seeded' not in existing_cols:
                batch_op.add_column(sa.Column('is_seeded', sa.Boolean(), server_default=sa.false(), nullable=False))
            if 'is_demo' not in existing_cols:
                batch_op.add_column(sa.Column('is_demo', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'actions' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('actions')}
        with op.batch_alter_table('actions', schema=None) as batch_op:
            if 'is_demo' in existing_cols:
                batch_op.drop_column('is_demo')
            if 'is_seeded' in existing_cols:
                batch_op.drop_column('is_seeded')
            if 'execution_error' in existing_cols:
                batch_op.drop_column('execution_error')
            if 'provider_request_id' in existing_cols:
                batch_op.drop_column('provider_request_id')

    if 'rescue_plans' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('rescue_plans')}
        with op.batch_alter_table('rescue_plans', schema=None) as batch_op:
            if 'is_demo' in existing_cols:
                batch_op.drop_column('is_demo')

    if 'obligations' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('obligations')}
        with op.batch_alter_table('obligations', schema=None) as batch_op:
            if 'is_demo' in existing_cols:
                batch_op.drop_column('is_demo')

    if 'invoices' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('invoices')}
        with op.batch_alter_table('invoices', schema=None) as batch_op:
            if 'provider_status' in existing_cols:
                batch_op.drop_column('provider_status')
            if 'invoice_number' in existing_cols:
                batch_op.drop_column('invoice_number')
            if 'is_seeded' in existing_cols:
                batch_op.drop_column('is_seeded')

