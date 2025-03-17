"""Initial migration

Revision ID: 0b2c965f95be
Revises: 
Create Date: 2025-03-17 09:35:56.323449

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0b2c965f95be'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('priority',
               existing_type=postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', name='taskpriority'),
               nullable=False)

    with op.batch_alter_table('user_roles', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'roles', ['role_name'], ['name'])

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('role')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.VARCHAR(length=50), autoincrement=False, nullable=False))

    with op.batch_alter_table('user_roles', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('priority',
               existing_type=postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', name='taskpriority'),
               nullable=True)

    # ### end Alembic commands ###
