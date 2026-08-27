"""Phase 11: create order_item_components table and add price_override to order_items

Revision ID: 14e6f7a1b2c3
Revises: 13d5e6f7a1b2
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14e6f7a1b2c3'
down_revision: Union[str, Sequence[str], None] = '13d5e6f7a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create order_item_components table
    op.create_table('order_item_components',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_item_id', sa.Integer(), nullable=False),
    sa.Column('deal_component_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('product_name', sa.String(length=150), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('size_id', sa.Integer(), nullable=True),
    sa.Column('was_removed', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('removed_reason', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['deal_component_id'], ['deal_components.id']),
    sa.ForeignKeyConstraint(['product_id'], ['products.id']),
    sa.ForeignKeyConstraint(['size_id'], ['product_sizes.id']),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('order_item_components', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_item_components_order_item_id'), ['order_item_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_order_item_components_deal_component_id'), ['deal_component_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_order_item_components_product_id'), ['product_id'], unique=False)

    # Add deal_id and price_override columns to order_items
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deal_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('price_override', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_order_items_deal_id', 'products', ['deal_id'], ['id'])


def downgrade() -> None:
    # Remove deal_id and price_override columns from order_items
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_order_items_deal_id', type_='foreignkey')
        batch_op.drop_column('price_override')
        batch_op.drop_column('deal_id')

    # Drop order_item_components table
    op.drop_table('order_item_components')
