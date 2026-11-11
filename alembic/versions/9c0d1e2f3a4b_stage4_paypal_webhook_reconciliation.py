"""stage4_paypal_webhook_reconciliation

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-11-11 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = '9c0d1e2f3a4b'
down_revision: Union[str, Sequence[str], None] = '8b9c0d1e2f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Update paypal_connections table
    if 'paypal_connections' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('paypal_connections')}
        with op.batch_alter_table('paypal_connections', schema=None) as batch_op:
            if 'connection_type' not in existing_cols:
                batch_op.add_column(sa.Column('connection_type', sa.String(50), server_default='shared_sandbox', nullable=False))
            if 'is_shared_sandbox' not in existing_cols:
                batch_op.add_column(sa.Column('is_shared_sandbox', sa.Boolean(), server_default=sa.true(), nullable=False))
            if 'merchant_id' not in existing_cols:
                batch_op.add_column(sa.Column('merchant_id', sa.String(100), nullable=True))
            if 'merchant_email' not in existing_cols:
                batch_op.add_column(sa.Column('merchant_email', sa.String(255), nullable=True))
            if 'webhook_id' not in existing_cols:
                batch_op.add_column(sa.Column('webhook_id', sa.String(100), nullable=True))

    # 2. Update webhook_events table
    if 'webhook_events' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('webhook_events')}
        with op.batch_alter_table('webhook_events', schema=None) as batch_op:
            if 'max_retries' not in existing_cols:
                batch_op.add_column(sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False))
            if 'locked_at' not in existing_cols:
                batch_op.add_column(sa.Column('locked_at', sa.DateTime(), nullable=True))
            if 'locked_by' not in existing_cols:
                batch_op.add_column(sa.Column('locked_by', sa.String(100), nullable=True))

    # 3. Create paypal_webhook_registrations table if not exists
    if 'paypal_webhook_registrations' not in existing_tables:
        op.create_table(
            'paypal_webhook_registrations',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('webhook_id', sa.String(100), unique=True, nullable=False, index=True),
            sa.Column('url', sa.String(500), nullable=False),
            sa.Column('environment', sa.String(50), server_default='sandbox', nullable=False),
            sa.Column('status', sa.String(50), server_default='active', nullable=False),
            sa.Column('event_types', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_verified_at', sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'paypal_webhook_registrations' in existing_tables:
        op.drop_table('paypal_webhook_registrations')

    if 'webhook_events' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('webhook_events')}
        with op.batch_alter_table('webhook_events', schema=None) as batch_op:
            if 'locked_by' in existing_cols:
                batch_op.drop_column('locked_by')
            if 'locked_at' in existing_cols:
                batch_op.drop_column('locked_at')
            if 'max_retries' in existing_cols:
                batch_op.drop_column('max_retries')

    if 'paypal_connections' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('paypal_connections')}
        with op.batch_alter_table('paypal_connections', schema=None) as batch_op:
            if 'webhook_id' in existing_cols:
                batch_op.drop_column('webhook_id')
            if 'merchant_email' in existing_cols:
                batch_op.drop_column('merchant_email')
            if 'merchant_id' in existing_cols:
                batch_op.drop_column('merchant_id')
            if 'is_shared_sandbox' in existing_cols:
                batch_op.drop_column('is_shared_sandbox')
            if 'connection_type' in existing_cols:
                batch_op.drop_column('connection_type')

