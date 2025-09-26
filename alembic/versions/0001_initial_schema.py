import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # This project manages schema via SQL file; treat this as baseline.
    pass


def downgrade():
    pass
