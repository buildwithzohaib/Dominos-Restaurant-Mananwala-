"""stage 7: add sessions table for token storage

Revision ID: e8f3dc45e6f7
Revises: d7e2cb34d5e6
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f3dc45e6f7'
down_revision: Union[str, Sequence[str], None] = 'd7e2cb34d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sessions table for storing active login tokens
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('expires_at', sa.DateTime, nullable=False),
    )
    op.create_index('ix_sessions_token', 'sessions', ['token'], unique=True)
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_sessions_user_id', 'sessions')
    op.drop_index('ix_sessions_token', 'sessions')
    op.drop_table('sessions')
