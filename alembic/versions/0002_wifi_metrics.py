"""Add optional manual label and bounded Wi-Fi telemetry.
Revision ID: 0002_wifi_metrics
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0002_wifi_metrics"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("network_checks", sa.Column("network_label", sa.String(40), nullable=True))
    op.add_column("network_checks", sa.Column("wifi_metrics", postgresql.JSONB(), nullable=True))
    op.create_check_constraint("ck_checks_label", "network_checks", "network_label IS NULL OR (length(network_label) BETWEEN 1 AND 40 AND network_label = btrim(network_label) AND network_label !~ '[[:cntrl:]]')")
    op.create_check_constraint("ck_checks_metrics_object", "network_checks", "wifi_metrics IS NULL OR jsonb_typeof(wifi_metrics) = 'object'")
    op.create_check_constraint("ck_checks_metrics_keys", "network_checks", "wifi_metrics IS NULL OR (wifi_metrics - ARRAY['rssi_dbm','frequency_mhz','wifi_standard','link_speed_mbps','tx_link_speed_mbps','rx_link_speed_mbps','internet_validated']) = '{}'::jsonb")
    op.create_check_constraint("ck_checks_metrics_size", "network_checks", "wifi_metrics IS NULL OR octet_length(wifi_metrics::text) <= 1024")

def downgrade():
    for name in ["ck_checks_metrics_size", "ck_checks_metrics_keys", "ck_checks_metrics_object", "ck_checks_label"]:
        op.drop_constraint(name, "network_checks", type_="check")
    op.drop_column("network_checks", "wifi_metrics")
    op.drop_column("network_checks", "network_label")
