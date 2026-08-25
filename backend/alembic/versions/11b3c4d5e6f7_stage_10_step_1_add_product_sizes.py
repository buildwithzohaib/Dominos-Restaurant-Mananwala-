"""Stage 10 step 1: add product sizes

Revision ID: 11b3c4d5e6f7
Revises: 10a2b3c4d5e6
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = '10a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create product_sizes table
    op.create_table('product_sizes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'name', name='uq_product_size_name')
    )
    with op.batch_alter_table('product_sizes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_product_sizes_product_id'), ['product_id'], unique=False)

    # Add size_name column to order_items (nullable, no default)
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('size_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # Drop size_name column from order_items
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.drop_column('size_name')

    # Drop product_sizes table
    op.drop_table('product_sizes')
