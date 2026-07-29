"""add tool counts to conversation messages

Revision ID: a6e4b91c2d73
Revises: 9f4c2d7a6b11
Create Date: 2026-07-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6e4b91c2d73"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "9f4c2d7a6b11"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    """Add per-message tool execution counters."""

    op.add_column(
        "conversation_messages",
        sa.Column(
            "tool_call_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    op.add_column(
        "conversation_messages",
        sa.Column(
            "successful_tool_call_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove per-message tool execution counters."""

    op.drop_column(
        "conversation_messages",
        "successful_tool_call_count",
    )

    op.drop_column(
        "conversation_messages",
        "tool_call_count",
    )