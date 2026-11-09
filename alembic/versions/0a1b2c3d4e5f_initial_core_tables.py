"""initial_core_tables

Revision ID: 0a1b2c3d4e5f
Revises: 
Create Date: 2026-11-05 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '0a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn) if hasattr(Inspector, "from_engine") else sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'owners' not in existing_tables:
        op.create_table(
            'owners',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('hashed_password', sa.String(length=255), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
            sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
            sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('owners', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_owners_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_owners_email'), ['email'], unique=True)

    if 'paypal_connections' not in existing_tables:
        op.create_table(
            'paypal_connections',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('environment', sa.String(length=50), nullable=False, server_default='sandbox'),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='connected'),
            sa.Column('last_checked_at', sa.DateTime(), nullable=True),
            sa.Column('client_id_preview', sa.String(length=50), nullable=True),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('owner_id')
        )
        with op.batch_alter_table('paypal_connections', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_paypal_connections_id'), ['id'], unique=False)

    if 'clients' not in existing_tables:
        op.create_table(
            'clients',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('country', sa.String(length=10), nullable=False, server_default='US'),
            sa.Column('typical_invoice_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='1000.00'),
            sa.Column('relationship_weight', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('is_seeded', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('clients', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_clients_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_clients_owner_id'), ['owner_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_clients_email'), ['email'], unique=False)

    if 'invoices' not in existing_tables:
        op.create_table(
            'invoices',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('paypal_invoice_id', sa.String(length=255), nullable=False),
            sa.Column('client_id', sa.Integer(), nullable=False),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
            sa.Column('issue_date', sa.DateTime(), nullable=False),
            sa.Column('due_date', sa.DateTime(), nullable=False),
            sa.Column('paid_date', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='SENT'),
            sa.Column('discount_applied', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.00'),
            sa.Column('pay_link', sa.String(length=1024), nullable=True),
            sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('invoices', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_invoices_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_invoices_paypal_invoice_id'), ['paypal_invoice_id'], unique=True)
            batch_op.create_index(batch_op.f('ix_invoices_client_id'), ['client_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_invoices_due_date'), ['due_date'], unique=False)

    if 'payment_history' not in existing_tables:
        op.create_table(
            'payment_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('client_id', sa.Integer(), nullable=False),
            sa.Column('invoice_id', sa.Integer(), nullable=True),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('due_date', sa.DateTime(), nullable=False),
            sa.Column('paid_date', sa.DateTime(), nullable=False),
            sa.Column('days_late', sa.Integer(), nullable=False),
            sa.Column('source', sa.String(length=50), nullable=False, server_default='paypal'),
            sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('payment_history', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_payment_history_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_payment_history_client_id'), ['client_id'], unique=False)

    if 'obligations' not in existing_tables:
        op.create_table(
            'obligations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('payee_name', sa.String(length=255), nullable=False),
            sa.Column('payee_email', sa.String(length=255), nullable=False),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
            sa.Column('due_date', sa.DateTime(), nullable=False),
            sa.Column('split_allowed', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('obligations', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_obligations_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_obligations_owner_id'), ['owner_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_obligations_due_date'), ['due_date'], unique=False)

    if 'financial_entries' not in existing_tables:
        op.create_table(
            'financial_entries',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
            sa.Column('entry_type', sa.String(length=50), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('recurrence', sa.String(length=50), nullable=False, server_default='one_time'),
            sa.Column('transaction_date', sa.DateTime(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='expected'),
            sa.Column('data_source', sa.String(length=50), nullable=False, server_default='manual'),
            sa.Column('reference_id', sa.String(length=255), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('financial_entries', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_financial_entries_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_financial_entries_owner_id'), ['owner_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_financial_entries_transaction_date'), ['transaction_date'], unique=False)

    if 'forecasts' not in existing_tables:
        op.create_table(
            'forecasts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('run_id', sa.String(length=100), nullable=False),
            sa.Column('obligation_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('starting_balance', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('horizon_days', sa.Integer(), nullable=False, server_default='14'),
            sa.Column('assumptions', sa.JSON(), nullable=False),
            sa.Column('projections', sa.JSON(), nullable=False),
            sa.Column('first_shortfall_date', sa.DateTime(), nullable=True),
            sa.Column('shortfall_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('p_shortfall', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('min_projected_balance', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('expected_income_total', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('expected_expense_total', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('driver_explanation', sa.Text(), nullable=True),
            sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('forecasts', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_forecasts_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_forecasts_run_id'), ['run_id'], unique=True)

    if 'client_predictions' not in existing_tables:
        op.create_table(
            'client_predictions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('run_id', sa.String(length=100), nullable=False),
            sa.Column('client_id', sa.Integer(), nullable=False),
            sa.Column('expected_pay_date', sa.DateTime(), nullable=False),
            sa.Column('p_late', sa.Float(), nullable=False),
            sa.Column('expected_days_late', sa.Float(), nullable=False),
            sa.Column('ci_low', sa.Float(), nullable=False),
            sa.Column('ci_high', sa.Float(), nullable=False),
            sa.Column('is_cold_start', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('client_predictions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_client_predictions_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_client_predictions_run_id'), ['run_id'], unique=False)

    if 'rescue_plans' not in existing_tables:
        op.create_table(
            'rescue_plans',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('run_id', sa.String(length=100), nullable=False),
            sa.Column('plan_type', sa.String(length=10), nullable=False),
            sa.Column('details', sa.JSON(), nullable=False),
            sa.Column('cost', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('incoming_needed', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('shortfall_probability_after', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('selected_clients', sa.JSON(), nullable=False),
            sa.Column('rationale', sa.Text(), nullable=False),
            sa.Column('forecast_with_plan', sa.JSON(), nullable=False),
            sa.Column('forecast_without_plan', sa.JSON(), nullable=False),
            sa.Column('late_scenario', sa.JSON(), nullable=False),
            sa.Column('remaining_risk', sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('rescue_plans', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_rescue_plans_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_rescue_plans_run_id'), ['run_id'], unique=False)

    if 'actions' not in existing_tables:
        op.create_table(
            'actions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('plan_id', sa.Integer(), nullable=True),
            sa.Column('action_type', sa.String(length=100), nullable=False),
            sa.Column('recipient', sa.String(length=255), nullable=False),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
            sa.Column('state', sa.String(length=50), nullable=False, server_default='proposed'),
            sa.Column('idempotency_key', sa.String(length=255), nullable=False),
            sa.Column('approval_hash', sa.String(length=255), nullable=False),
            sa.Column('paypal_ref', sa.String(length=255), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('executed_at', sa.DateTime(), nullable=True),
            sa.Column('confirmed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['plan_id'], ['rescue_plans.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('actions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_actions_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_actions_idempotency_key'), ['idempotency_key'], unique=True)

    if 'messages' not in existing_tables:
        op.create_table(
            'messages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('action_id', sa.Integer(), nullable=True),
            sa.Column('client_id', sa.Integer(), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('approval_status', sa.String(length=50), nullable=False, server_default='draft'),
            sa.ForeignKeyConstraint(['action_id'], ['actions.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('messages', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_messages_id'), ['id'], unique=False)

    if 'negotiation_drafts' not in existing_tables:
        op.create_table(
            'negotiation_drafts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('client_id', sa.Integer(), nullable=True),
            sa.Column('obligation_id', sa.Integer(), nullable=True),
            sa.Column('target_type', sa.String(length=50), nullable=False),
            sa.Column('recipient_name', sa.String(length=255), nullable=False),
            sa.Column('recipient_email', sa.String(length=255), nullable=False),
            sa.Column('tone', sa.String(length=50), nullable=False, server_default='professional'),
            sa.Column('subject', sa.String(length=255), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('offered_incentive', sa.String(length=255), nullable=True),
            sa.Column('estimated_benefit', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('negotiation_drafts', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_negotiation_drafts_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_negotiation_drafts_owner_id'), ['owner_id'], unique=False)

    if 'simulation_runs' not in existing_tables:
        op.create_table(
            'simulation_runs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('run_name', sa.String(length=255), nullable=False),
            sa.Column('scenario_type', sa.String(length=100), nullable=False),
            sa.Column('parameters', sa.JSON(), nullable=False),
            sa.Column('baseline_metrics', sa.JSON(), nullable=False),
            sa.Column('simulated_metrics', sa.JSON(), nullable=False),
            sa.Column('delta_metrics', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('simulation_runs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_simulation_runs_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_simulation_runs_owner_id'), ['owner_id'], unique=False)

    if 'agent_workflow_runs' not in existing_tables:
        op.create_table(
            'agent_workflow_runs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('run_id', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='running'),
            sa.Column('steps_trace', sa.JSON(), nullable=False),
            sa.Column('selected_plan', sa.String(length=10), nullable=True),
            sa.Column('final_recommendation', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('agent_workflow_runs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_agent_workflow_runs_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_agent_workflow_runs_owner_id'), ['owner_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_agent_workflow_runs_run_id'), ['run_id'], unique=True)

    if 'audit_log' not in existing_tables:
        op.create_table(
            'audit_log',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('ts', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('actor', sa.String(length=100), nullable=False),
            sa.Column('event', sa.String(length=100), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('prev_hash', sa.String(length=64), nullable=False),
            sa.Column('hash', sa.String(length=64), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('audit_log', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_audit_log_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_audit_log_ts'), ['ts'], unique=False)
            batch_op.create_index(batch_op.f('ix_audit_log_event'), ['event'], unique=False)
            batch_op.create_index(batch_op.f('ix_audit_log_hash'), ['hash'], unique=False)

    if 'webhook_events' not in existing_tables:
        op.create_table(
            'webhook_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('paypal_event_id', sa.String(length=255), nullable=False),
            sa.Column('event_type', sa.String(length=100), nullable=False),
            sa.Column('verified', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('received_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('is_simulated', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('webhook_events', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_webhook_events_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_webhook_events_paypal_event_id'), ['paypal_event_id'], unique=True)
            batch_op.create_index(batch_op.f('ix_webhook_events_event_type'), ['event_type'], unique=False)
            batch_op.create_index(batch_op.f('ix_webhook_events_processed'), ['processed'], unique=False)


def downgrade() -> None:
    pass
