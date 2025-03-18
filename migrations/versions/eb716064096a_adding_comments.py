"""Adding comments

Revision ID: eb716064096a
Revises: a0608d7fa755
Create Date: 2025-03-17 15:14:35.779412

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'eb716064096a'
down_revision = 'a0608d7fa755'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('task_comments')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('task_comments',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('task_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('user_email', sa.VARCHAR(length=120), autoincrement=False, nullable=False),
    sa.Column('content', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('is_edited', sa.BOOLEAN(), autoincrement=False, nullable=True),
    sa.Column('edited_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name='task_comments_task_id_fkey'),
    sa.ForeignKeyConstraint(['user_email'], ['users.email'], name='task_comments_user_email_fkey'),
    sa.PrimaryKeyConstraint('id', name='task_comments_pkey')
    )
    # ### end Alembic commands ###
