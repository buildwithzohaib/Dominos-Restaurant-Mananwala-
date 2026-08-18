"""stage 4 a1: open orders, batch_id, partial unique index

Revision ID: ad8ba306eabb
Revises: c6496349064a
Create Date: 2026-08-18 11:09:30.928169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad8ba306eabb'
down_revision: Union[str, Sequence[str], None] = 'c6496349064a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # order_items: batch_id (NULL = PENDING, 1/2/3 = sent in that batch)
    op.add_column('order_items', sa.Column('batch_id', sa.Integer(), nullable=True))

    # order_items: sent_at (NULL until the batch is sent to kitchen)
    op.add_column('order_items', sa.Column('sent_at', sa.DateTime(), nullable=True))

    # orders.payment_method -> nullable. NULL means "not yet paid".
    # SQLite cannot drop NOT NULL in place, so this rebuilds the table.
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('payment_method',
                              existing_type=sa.String(30),
                              existing_nullable=False,
                              nullable=True)

    # Partial unique index MUST come after the batch block:
    # the rebuild above would otherwise drop it.
    op.create_index('ix_one_open_per_table', 'orders', ['table_id'],
                    unique=True, sqlite_where=sa.text("status = 'OPEN'"))


def downgrade() -> None:
    # Note: restoring NOT NULL on payment_method will fail if any order has
    # payment_method IS NULL at that moment (i.e. any OPEN order exists).
    # This is intended. Close or cancel open orders before downgrading.
    op.drop_index('ix_one_open_per_table', table_name='orders')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('payment_method',
                              existing_type=sa.String(30),
                              existing_nullable=True,
                              nullable=False)

    op.drop_column('order_items', 'sent_at')
    op.drop_column('order_items', 'batch_id')
