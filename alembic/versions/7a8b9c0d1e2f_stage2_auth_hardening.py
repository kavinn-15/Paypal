"""stage2_auth_hardening

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
Create Date: 2026-11-11 11:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '6f7a8b9c0d1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Update owners table
    if 'owners' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('owners')}
        cols_to_add = []

        if 'terms_accepted' not in existing_cols:
            cols_to_add.append(sa.Column('terms_accepted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        if 'terms_accepted_at' not in existing_cols:
            cols_to_add.append(sa.Column('terms_accepted_at', sa.DateTime(), nullable=True))
        if 'token_version' not in existing_cols:
            cols_to_add.append(sa.Column('token_version', sa.Integer(), nullable=False, server_default=sa.text('1')))

        if cols_to_add:
            with op.batch_alter_table('owners', schema=None) as batch_op:
                for col in cols_to_add:
                    batch_op.add_column(col)

    # 2. Update refresh_tokens table
    if 'refresh_tokens' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('refresh_tokens')}
        if 'family_id' not in existing_cols:
            with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
                batch_op.add_column(sa.Column('family_id', sa.String(length=100), nullable=True))
                batch_op.create_index('ix_refresh_tokens_family_id', ['family_id'], unique=False)

    # 3. Create rate_limit_attempts table
    if 'rate_limit_attempts' not in existing_tables:
        op.create_table(
            'rate_limit_attempts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(length=255), nullable=False),
            sa.Column('attempt_time', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_rate_limit_attempts_key', 'rate_limit_attempts', ['key'], unique=False)
        op.create_index('ix_rate_limit_attempts_attempt_time', 'rate_limit_attempts', ['attempt_time'], unique=False)

    # 4. Create consumed_tokens table
    if 'consumed_tokens' not in existing_tables:
        op.create_table(
            'consumed_tokens',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('jti', sa.String(length=255), nullable=False),
            sa.Column('consumed_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_consumed_tokens_jti', 'consumed_tokens', ['jti'], unique=True)

    # 5. Create oauth_states table
    if 'oauth_states' not in existing_tables:
        op.create_table(
            'oauth_states',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('state', sa.String(length=255), nullable=False),
            sa.Column('code_verifier', sa.String(length=255), nullable=True),
            sa.Column('consumed', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_oauth_states_state', 'oauth_states', ['state'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'oauth_states' in existing_tables:
        op.drop_table('oauth_states')
    if 'consumed_tokens' in existing_tables:
        op.drop_table('consumed_tokens')
    if 'rate_limit_attempts' in existing_tables:
        op.drop_table('rate_limit_attempts')

    if 'refresh_tokens' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('refresh_tokens')}
        if 'family_id' in existing_cols:
            with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
                batch_op.drop_index('ix_refresh_tokens_family_id')
                batch_op.drop_column('family_id')

    if 'owners' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('owners')}
        with op.batch_alter_table('owners', schema=None) as batch_op:
            for c in ['terms_accepted', 'terms_accepted_at', 'token_version']:
                if c in existing_cols:
                    batch_op.drop_column(c)

