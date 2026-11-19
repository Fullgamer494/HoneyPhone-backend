"""Add device metadata and revocation state."""
from alembic import op
import sqlalchemy as sa

revision = "0003_device_registry"
down_revision = "0002_wifi_metrics"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("installations", sa.Column("device_name", sa.String(64), nullable=True))
    op.add_column("installations", sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False))

def downgrade():
    op.drop_column("installations", "active")
    op.drop_column("installations", "device_name")
