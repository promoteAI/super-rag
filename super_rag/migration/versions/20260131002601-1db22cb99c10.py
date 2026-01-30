"""rename bot to agent

Revision ID: 1db22cb99c10
Revises: 4abd1756eeda
Create Date: 2026-01-31 00:26:01.842573

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1db22cb99c10'
down_revision: Union[str, None] = '4abd1756eeda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("bot", "agent")
    op.drop_index("ix_bot_user", table_name="agent")
    op.drop_index("ix_bot_status", table_name="agent")
    op.drop_index("ix_bot_gmt_deleted", table_name="agent")
    op.create_index("ix_agent_user", "agent", ["user"], unique=False)
    op.create_index("ix_agent_status", "agent", ["status"], unique=False)
    op.create_index("ix_agent_gmt_deleted", "agent", ["gmt_deleted"], unique=False)

    op.drop_constraint("uq_chat_bot_peer_deleted", "chat", type_="unique")
    op.drop_index("ix_chat_bot_id", table_name="chat")
    op.alter_column("chat", "bot_id", new_column_name="agent_id")
    op.create_index("ix_chat_agent_id", "chat", ["agent_id"], unique=False)
    op.create_unique_constraint(
        "uq_chat_agent_peer_deleted",
        "chat",
        ["agent_id", "peer_type", "peer_id", "gmt_deleted"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_chat_agent_peer_deleted", "chat", type_="unique")
    op.drop_index("ix_chat_agent_id", table_name="chat")
    op.alter_column("chat", "agent_id", new_column_name="bot_id")
    op.create_index("ix_chat_bot_id", "chat", ["bot_id"], unique=False)
    op.create_unique_constraint(
        "uq_chat_bot_peer_deleted",
        "chat",
        ["bot_id", "peer_type", "peer_id", "gmt_deleted"],
    )

    op.drop_index("ix_agent_gmt_deleted", table_name="agent")
    op.drop_index("ix_agent_status", table_name="agent")
    op.drop_index("ix_agent_user", table_name="agent")
    op.create_index("ix_bot_user", "agent", ["user"], unique=False)
    op.create_index("ix_bot_status", "agent", ["status"], unique=False)
    op.create_index("ix_bot_gmt_deleted", "agent", ["gmt_deleted"], unique=False)
    op.rename_table("agent", "bot")
