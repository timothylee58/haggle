"""Private, insert-only deal terms, kept out of the spectator event log.

Revision ID: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deal_terms",
        sa.Column("deal_id", sa.Uuid, primary_key=True),
        sa.Column("budget_cap_minor", sa.BigInteger, nullable=False),
    )
    op.execute(
        """
        CREATE TRIGGER deal_terms_no_change BEFORE UPDATE OR DELETE ON deal_terms
        FOR EACH ROW EXECUTE FUNCTION deal_events_append_only()
        """
    )


def downgrade() -> None:
    op.drop_table("deal_terms")
