"""Create the append-only deal event log.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deal_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("deal_id", sa.Uuid, nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("deal_id", "seq", name="uq_deal_events_deal_seq"),
    )
    op.execute(
        """
        CREATE FUNCTION deal_events_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'deal_events is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER deal_events_no_change BEFORE UPDATE OR DELETE ON deal_events
        FOR EACH ROW EXECUTE FUNCTION deal_events_append_only()
        """
    )
    op.execute(
        """
        CREATE TRIGGER deal_events_no_truncate BEFORE TRUNCATE ON deal_events
        FOR EACH STATEMENT EXECUTE FUNCTION deal_events_append_only()
        """
    )


def downgrade() -> None:
    op.drop_table("deal_events")
    op.execute("DROP FUNCTION deal_events_append_only")
