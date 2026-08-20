"""stage 7: add users table and attribution columns

Revision ID: d6f0ab23c4e5
Revises: b3d5e7f9a1c3
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6f0ab23c4e5'
down_revision: Union[str, Sequence[str], None] = 'b3d5e7f9a1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('pin', sa.String(10), nullable=False),
        sa.Column('can_cancel', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('can_discount', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('can_manage_settings', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('name', 'pin', name='uq_users_name_pin'),
    )

    # Add performed_by_user_id for payment/discount attribution
    op.add_column('orders', sa.Column('performed_by_user_id', sa.Integer, nullable=True))
    op.create_foreign_key(
        'fk_orders_performed_by_user_id',
        'orders', 'users',
        ['performed_by_user_id'], ['id']
    )

    # Add cancel_order_performed_by_user_id for cancellation attribution
    op.add_column('orders', sa.Column('cancel_order_performed_by_user_id', sa.Integer, nullable=True))
    op.create_foreign_key(
        'fk_orders_cancel_order_performed_by_user_id',
        'orders', 'users',
        ['cancel_order_performed_by_user_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_orders_cancel_order_performed_by_user_id', 'orders')
    op.drop_column('orders', 'cancel_order_performed_by_user_id')
    op.drop_constraint('fk_orders_performed_by_user_id', 'orders')
    op.drop_column('orders', 'performed_by_user_id')
    op.drop_table('users')
