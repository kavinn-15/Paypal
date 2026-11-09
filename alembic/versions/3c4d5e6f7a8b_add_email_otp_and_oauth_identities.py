"""add_email_otp_and_oauth_identities

Revision ID: 3c4d5e6f7a8b
Revises: 2b8f7e91a0c3
Create Date: 2026-11-07 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c4d5e6f7a8b'
down_revision: Union[str, Sequence[str], None] = '2b8f7e91a0c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())
    existing_owner_cols = {col['name'] for col in inspector.get_columns('owners')} if 'owners' in existing_tables else set()

    # 1. Add email_verified_at to owners
    if 'email_verified_at' not in existing_owner_cols:
        with op.batch_alter_table('owners', schema=None) as batch_op:
            batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(), nullable=True))

    # 2. Create email_otps table
    if 'email_otps' not in existing_tables:
        op.create_table(
            'email_otps',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('otp_hash', sa.String(length=255), nullable=False),
            sa.Column('purpose', sa.String(length=50), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('attempts_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'),
            sa.Column('consumed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('email_otps', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_email_otps_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_email_otps_owner_id'), ['owner_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_email_otps_email'), ['email'], unique=False)

    # 3. Create oauth_identities table
    if 'oauth_identities' not in existing_tables:
        op.create_table(
            'oauth_identities',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('provider_user_id', sa.String(length=255), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['owner_id'], ['owners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_user')
        )
        with op.batch_alter_table('oauth_identities', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_oauth_identities_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_oauth_identities_owner_id'), ['owner_id'], unique=False)
            batch_op.create_index('ix_oauth_identities_provider_sub', ['provider', 'provider_user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('oauth_identities')
    op.drop_table('email_otps')
    with op.batch_alter_table('owners', schema=None) as batch_op:
        batch_op.drop_column('email_verified_at')

