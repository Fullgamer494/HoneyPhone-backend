"""Add user accounts and installation ownership."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_accounts"
down_revision = "0003_device_registry"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=True),
        sa.Column("google_subject", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("google_subject", name="uq_users_google_subject"),
    )
    op.add_column("installations", sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_installations_owner_user", "installations", "users", ["owner_user_id"], ["user_id"], ondelete="SET NULL")
    op.create_index("ix_installations_owner_user_id", "installations", ["owner_user_id"])


def downgrade():
    op.drop_index("ix_installations_owner_user_id", table_name="installations")
    op.drop_constraint("fk_installations_owner_user", "installations", type_="foreignkey")
    op.drop_column("installations", "owner_user_id")
    op.drop_table("users")
