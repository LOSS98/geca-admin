"""Initial migration

Revision ID: bfbe7f7e14e6
Revises: 
Create Date: 2024-12-03 00:25:02.865627

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bfbe7f7e14e6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'users', ['added_by'], ['email'])

    with op.batch_alter_table('incomes', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'users', ['added_by'], ['email'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('incomes', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    # ### end Alembic commands ###
