"""userserie table

Revision ID: be927e025a98
Revises: d8fa5dd60412
Create Date: 2019-11-10 11:38:07.474872

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'be927e025a98'
down_revision = 'd8fa5dd60412'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_media',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('media', sa.String(), nullable=True),
    sa.Column('media_id', sa.Integer(), nullable=True),
    sa.Column('season_id', sa.Integer(), nullable=True),
    sa.Column('episode_id', sa.Integer(), nullable=True),
    sa.Column('state_serie', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_media')
    # ### end Alembic commands ###
