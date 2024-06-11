"""Added free and paid credits in user model

Revision ID: a5313b5dd408
Revises: 1e93786bf0d6
Create Date: 2024-06-08 21:15:07.303741

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5313b5dd408'
down_revision = '1e93786bf0d6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('free_credits', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('paid_credits', sa.Integer(), nullable=True))
        batch_op.drop_column('credits')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('credits', sa.INTEGER(), nullable=True))
        batch_op.drop_column('paid_credits')
        batch_op.drop_column('free_credits')

    # ### end Alembic commands ###
