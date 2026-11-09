"""add_phone_auth_and_phone_otps

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-11-07 10:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d5e6f7a8b9c'
down_revision: Union[str, Sequence[str], None] = '3c4d5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())
    existing_owner_cols = {col['name'] for col in inspector.get_columns('owners')} if 'owners' in existing_tables else set()

    # 1. Add phone columns to owners
    owner_phone_cols = [
        ('phone_number', sa.Column('phone_number', sa.String(length=32), nullable=True)),
        ('phone_country_code', sa.Column('phone_country_code', sa.String(length=8), nullable=True, server_default='+91')),
        ('phone_verified', sa.Column('phone_verified', sa.Boolean(), nullable=False, server_default=sa.text('0'))),
        ('phone_verified_at', sa.Column('phone_verified_at', sa.DateTime(), nullable=True)),
    ]
    missing_owner_cols = [(cname, ccol) for cname, ccol in owner_phone_cols if cname not in existing_owner_cols]
    if missing_owner_cols:
        with op.batch_alter_table('owners', schema=None) as batch_op:
            for cname, ccol in missing_owner_cols:
                batch_op.add_column(ccol)
            existing_indices = {idx['name'] for idx in inspector.get_indexes('owners')}
            if 'ix_owners_phone_number' not in existing_indices:
                batch_op.create_index(batch_op.f('ix_owners_phone_number'), ['phone_number'], unique=True)

    # 2. Create phone_otps table
    if 'phone_otps' not in existing_tables:
        op.create_table(
            'phone_otps',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=True),
            sa.Column('phone_number', sa.String(length=32), nullable=False),
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
        with op.batch_alter_table('phone_otps', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_phone_otps_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_phone_otps_owner_id'), ['owner_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_phone_otps_phone_number'), ['phone_number'], unique=False)
            batch_op.create_index('ix_phone_otps_phone_purpose', ['phone_number', 'purpose'], unique=False)


def downgrade() -> None:
    op.drop_table('phone_otps')
    with op.batch_alter_table('owners', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_owners_phone_number'))
        batch_op.drop_column('phone_verified_at')
        batch_op.drop_column('phone_verified')
        batch_op.drop_column('phone_country_code')
        batch_op.drop_column('phone_number')

