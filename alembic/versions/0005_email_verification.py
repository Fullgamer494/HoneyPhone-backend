"""Add account email verification and one-time action tokens."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_email_actions"
down_revision = "0004_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "account_action_tokens",
        sa.Column("token_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_account_action_tokens_token_hash"),
    )
    op.create_index("ix_account_action_tokens_user_id", "account_action_tokens", ["user_id"])
    op.create_index("ix_account_action_tokens_purpose", "account_action_tokens", ["purpose"])


def downgrade():
    op.drop_index("ix_account_action_tokens_purpose", table_name="account_action_tokens")
    op.drop_index("ix_account_action_tokens_user_id", table_name="account_action_tokens")
    op.drop_table("account_action_tokens")
    op.drop_column("users", "email_verified_at")
