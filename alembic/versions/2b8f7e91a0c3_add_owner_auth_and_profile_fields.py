"""add_owner_auth_and_profile_fields

Revision ID: 2b8f7e91a0c3
Revises: 1c0b99d5f965
Create Date: 2026-11-07 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b8f7e91a0c3'
down_revision: Union[str, Sequence[str], None] = '1c0b99d5f965'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('owners', schema=None) as batch_op:
        batch_op.add_column(sa.Column('country', sa.String(length=50), nullable=True, server_default='US'))
        batch_op.add_column(sa.Column('business_type', sa.String(length=50), nullable=True, server_default='Freelancer'))
        batch_op.add_column(sa.Column('preferred_currency', sa.String(length=10), nullable=True, server_default='USD'))
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('account_status', sa.String(length=20), nullable=False, server_default='active'))
        batch_op.add_column(sa.Column('password_reset_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('reset_token_expires_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('email_verification_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
        batch_op.create_index('ix_owners_password_reset_token', ['password_reset_token'], unique=False)
        batch_op.create_index('ix_owners_email_verification_token', ['email_verification_token'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('owners', schema=None) as batch_op:
        batch_op.drop_index('ix_owners_email_verification_token')
        batch_op.drop_index('ix_owners_password_reset_token')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('email_verification_token')
        batch_op.drop_column('reset_token_expires_at')
        batch_op.drop_column('password_reset_token')
        batch_op.drop_column('account_status')
        batch_op.drop_column('email_verified')
        batch_op.drop_column('preferred_currency')
        batch_op.drop_column('business_type')
        batch_op.drop_column('country')

