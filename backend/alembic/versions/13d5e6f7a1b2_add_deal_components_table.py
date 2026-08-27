"""Phase 11: create deal_components table for deal product definitions

Revision ID: 13d5e6f7a1b2
Revises: 12c4d5e6f7a1
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13d5e6f7a1b2'
down_revision: Union[str, Sequence[str], None] = '12c4d5e6f7a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create deal_components table
    op.create_table('deal_components',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('component_product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('size_id', sa.Integer(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id']),
    sa.ForeignKeyConstraint(['component_product_id'], ['products.id']),
    sa.ForeignKeyConstraint(['size_id'], ['product_sizes.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'component_product_id', 'size_id', name='uq_deal_component')
    )
    with op.batch_alter_table('deal_components', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deal_components_product_id'), ['product_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_deal_components_component_product_id'), ['component_product_id'], unique=False)


def downgrade() -> None:
    # Drop deal_components table
    op.drop_table('deal_components')
