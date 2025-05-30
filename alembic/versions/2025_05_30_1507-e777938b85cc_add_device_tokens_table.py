"""add device tokens table

Revision ID: e777938b85cc
Revises: d0e21926e0da
Create Date: 2025-05-30 15:07:45.685883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e777938b85cc'
down_revision: Union[str, None] = 'd0e21926e0da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create device_tokens table
    op.create_table('device_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('device_name', sa.String(), nullable=True),
        sa.Column('device_model', sa.String(), nullable=True),
        sa.Column('os_version', sa.String(), nullable=True),
        sa.Column('app_version', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    
    # Create indexes
    op.create_index('idx_device_tokens_user_id', 'device_tokens', ['user_id'])
    op.create_index('idx_device_tokens_token', 'device_tokens', ['token'])
    op.create_index('idx_device_tokens_user_platform', 'device_tokens', ['user_id', 'platform'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_device_tokens_user_platform', table_name='device_tokens')
    op.drop_index('idx_device_tokens_token', table_name='device_tokens')
    op.drop_index('idx_device_tokens_user_id', table_name='device_tokens')
    
    # Drop table
    op.drop_table('device_tokens')