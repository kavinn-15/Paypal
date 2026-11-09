"""add_regional_preferences

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-11-10 00:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f7a8b9c0d1e'
down_revision: Union[str, Sequence[str], None] = '5e6f7a8b9c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'owners' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('owners')}
        cols_to_add = []

        if 'country' not in existing_cols:
            cols_to_add.append(sa.Column('country', sa.String(length=50), nullable=True, server_default='US'))
        if 'preferred_currency' not in existing_cols:
            cols_to_add.append(sa.Column('preferred_currency', sa.String(length=10), nullable=True, server_default='USD'))
        if 'locale' not in existing_cols:
            cols_to_add.append(sa.Column('locale', sa.String(length=10), nullable=False, server_default='en-US'))
        if 'region_detection_enabled' not in existing_cols:
            cols_to_add.append(sa.Column('region_detection_enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        if 'region_preference_source' not in existing_cols:
            cols_to_add.append(sa.Column('region_preference_source', sa.String(length=30), nullable=False, server_default='detected'))
        if 'region_preferences_updated_at' not in existing_cols:
            cols_to_add.append(sa.Column('region_preferences_updated_at', sa.DateTime(), nullable=True))

        if cols_to_add:
            with op.batch_alter_table('owners', schema=None) as batch_op:
                for col in cols_to_add:
                    batch_op.add_column(col)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'owners' in existing_tables:
        existing_cols = {col['name'] for col in inspector.get_columns('owners')}
        with op.batch_alter_table('owners', schema=None) as batch_op:
            for c in ['region_preferences_updated_at', 'region_preference_source', 'region_detection_enabled', 'locale']:
                if c in existing_cols:
                    batch_op.drop_column(c)

