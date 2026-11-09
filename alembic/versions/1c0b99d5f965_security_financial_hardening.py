"""security_financial_hardening

Revision ID: 1c0b99d5f965
Revises: 
Create Date: 2026-11-06 15:56:18.217888

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c0b99d5f965'
down_revision: Union[str, Sequence[str], None] = '0a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'exchange_rates' not in existing_tables:
        op.create_table('exchange_rates',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('from_currency', sa.String(length=10), nullable=False),
            sa.Column('to_currency', sa.String(length=10), nullable=False),
            sa.Column('rate', sa.Numeric(precision=18, scale=6), nullable=False),
            sa.Column('source', sa.String(length=100), nullable=False),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('from_currency', 'to_currency', name='uq_from_to_currency')
        )
        with op.batch_alter_table('exchange_rates', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_exchange_rates_from_currency'), ['from_currency'], unique=False)
            batch_op.create_index(batch_op.f('ix_exchange_rates_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_exchange_rates_to_currency'), ['to_currency'], unique=False)

    if 'refresh_tokens' not in existing_tables:
        op.create_table('refresh_tokens',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('token', sa.String(length=255), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('revoked', sa.Boolean(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_refresh_tokens_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_refresh_tokens_owner_id'), ['owner_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_refresh_tokens_token'), ['token'], unique=True)

    action_cols = {col['name'] for col in inspector.get_columns('actions')} if 'actions' in existing_tables else set()
    if 'owner_id' not in action_cols:
        with op.batch_alter_table('actions', schema=None) as batch_op:
            batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_actions_owner_id'), ['owner_id'], unique=False)
            batch_op.create_foreign_key('fk_actions_owner_id_owners', 'owners', ['owner_id'], ['id'], ondelete='CASCADE')

    audit_cols = {col['name'] for col in inspector.get_columns('audit_log')} if 'audit_log' in existing_tables else set()
    if 'owner_id' not in audit_cols:
        with op.batch_alter_table('audit_log', schema=None) as batch_op:
            batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_audit_log_owner_id'), ['owner_id'], unique=False)
            batch_op.create_foreign_key('fk_audit_log_owner_id_owners', 'owners', ['owner_id'], ['id'], ondelete='CASCADE')

    fe_cols = {col['name'] for col in inspector.get_columns('financial_entries')} if 'financial_entries' in existing_tables else set()
    with op.batch_alter_table('financial_entries', schema=None) as batch_op:
        if 'canonical_id' not in fe_cols:
            batch_op.add_column(sa.Column('canonical_id', sa.String(length=255), nullable=True))
            batch_op.create_index(batch_op.f('ix_financial_entries_canonical_id'), ['canonical_id'], unique=True)
            batch_op.create_index(batch_op.f('ix_financial_entries_reference_id'), ['reference_id'], unique=False)
        if 'is_recurring' not in fe_cols:
            batch_op.add_column(sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        if 'recurrence_end_date' not in fe_cols:
            batch_op.add_column(sa.Column('recurrence_end_date', sa.DateTime(), nullable=True))
        if 'is_cancelled' not in fe_cols:
            batch_op.add_column(sa.Column('is_cancelled', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        if 'parent_entry_id' not in fe_cols:
            batch_op.add_column(sa.Column('parent_entry_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_financial_entries_parent_entry_id', 'financial_entries', ['parent_entry_id'], ['id'], ondelete='SET NULL')
        if 'reconciled' not in fe_cols:
            batch_op.add_column(sa.Column('reconciled', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    fc_cols = {col['name'] for col in inspector.get_columns('forecasts')} if 'forecasts' in existing_tables else set()
    if 'owner_id' not in fc_cols:
        with op.batch_alter_table('forecasts', schema=None) as batch_op:
            batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_forecasts_owner_id'), ['owner_id'], unique=False)
            batch_op.create_foreign_key('fk_forecasts_owner_id_owners', 'owners', ['owner_id'], ['id'], ondelete='CASCADE')

    rp_cols = {col['name'] for col in inspector.get_columns('rescue_plans')} if 'rescue_plans' in existing_tables else set()
    if 'owner_id' not in rp_cols:
        with op.batch_alter_table('rescue_plans', schema=None) as batch_op:
            batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_rescue_plans_owner_id'), ['owner_id'], unique=False)
            batch_op.create_foreign_key('fk_rescue_plans_owner_id_owners', 'owners', ['owner_id'], ['id'], ondelete='CASCADE')

    we_cols = {col['name'] for col in inspector.get_columns('webhook_events')} if 'webhook_events' in existing_tables else set()
    with op.batch_alter_table('webhook_events', schema=None) as batch_op:
        if 'owner_id' not in we_cols:
            batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_webhook_events_owner_id'), ['owner_id'], unique=False)
            batch_op.create_foreign_key('fk_webhook_events_owner_id_owners', 'owners', ['owner_id'], ['id'], ondelete='CASCADE')
        if 'processing_state' not in we_cols:
            batch_op.add_column(sa.Column('processing_state', sa.String(length=50), nullable=False, server_default='received'))
            batch_op.create_index(batch_op.f('ix_webhook_events_processing_state'), ['processing_state'], unique=False)
        if 'retry_count' not in we_cols:
            batch_op.add_column(sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
        if 'error_details' not in we_cols:
            batch_op.add_column(sa.Column('error_details', sa.Text(), nullable=True))
        if 'processed_at' not in we_cols:
            batch_op.add_column(sa.Column('processed_at', sa.DateTime(), nullable=True))
        if 'reconciliation_status' not in we_cols:
            batch_op.add_column(sa.Column('reconciliation_status', sa.String(length=50), nullable=False, server_default='pending'))

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('webhook_events', schema=None) as batch_op:
        # WARNING: constraint name is None; this directive will fail as
        # rendered.  Add a name, or use a naming convention; see
        # https://alembic.sqlalchemy.org/en/latest/naming.html
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_webhook_events_processing_state'))
        batch_op.drop_index(batch_op.f('ix_webhook_events_owner_id'))
        batch_op.drop_column('reconciliation_status')
        batch_op.drop_column('processed_at')
        batch_op.drop_column('error_details')
        batch_op.drop_column('retry_count')
        batch_op.drop_column('processing_state')
        batch_op.drop_column('owner_id')

    with op.batch_alter_table('rescue_plans', schema=None) as batch_op:
        # WARNING: constraint name is None; this directive will fail as
        # rendered.  Add a name, or use a naming convention; see
        # https://alembic.sqlalchemy.org/en/latest/naming.html
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_rescue_plans_owner_id'))
        batch_op.drop_column('owner_id')

    with op.batch_alter_table('forecasts', schema=None) as batch_op:
        # WARNING: constraint name is None; this directive will fail as
        # rendered.  Add a name, or use a naming convention; see
        # https://alembic.sqlalchemy.org/en/latest/naming.html
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_forecasts_owner_id'))
        batch_op.drop_column('owner_id')

    with op.batch_alter_table('financial_entries', schema=None) as batch_op:
        # WARNING: constraint name is None; this directive will fail as
        # rendered.  Add a name, or use a naming convention; see
        # https://alembic.sqlalchemy.org/en/latest/naming.html
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_financial_entries_reference_id'))
        batch_op.drop_index(batch_op.f('ix_financial_entries_canonical_id'))
        batch_op.drop_column('reconciled')
        batch_op.drop_column('parent_entry_id')
        batch_op.drop_column('is_cancelled')
        batch_op.drop_column('recurrence_end_date')
        batch_op.drop_column('is_recurring')
        batch_op.drop_column('canonical_id')

    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        # WARNING: constraint name is None; this directive will fail as
        # rendered.  Add a name, or use a naming convention; see
        # https://alembic.sqlalchemy.org/en/latest/naming.html
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_audit_log_owner_id'))
        batch_op.drop_column('owner_id')

    with op.batch_alter_table('actions', schema=None) as batch_op:
        # WARNING: constraint name is None; this directive will fail as
        # rendered.  Add a name, or use a naming convention; see
        # https://alembic.sqlalchemy.org/en/latest/naming.html
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_actions_owner_id'))
        batch_op.drop_column('owner_id')

    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_token'))
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_owner_id'))
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_id'))

    op.drop_table('refresh_tokens')
    with op.batch_alter_table('exchange_rates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_exchange_rates_to_currency'))
        batch_op.drop_index(batch_op.f('ix_exchange_rates_id'))
        batch_op.drop_index(batch_op.f('ix_exchange_rates_from_currency'))

    op.drop_table('exchange_rates')
    # ### end Alembic commands ###
