"""Private, insert-only access tokens for deals.

Only a hash of each deal's owner token is stored. The token itself is shown once, to whoever started
the match, and it is what lets that person move money in the Shield. Spectators only watch.

Revision ID: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deal_access",
        sa.Column("deal_id", sa.Uuid, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
    )
    op.execute(
        """
        CREATE TRIGGER deal_access_no_change BEFORE UPDATE OR DELETE ON deal_access
        FOR EACH ROW EXECUTE FUNCTION deal_events_append_only()
        """
    )


def downgrade() -> None:
    op.drop_table("deal_access")
