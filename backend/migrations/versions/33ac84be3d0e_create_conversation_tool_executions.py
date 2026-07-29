"""create conversation tool executions

Revision ID: 33ac84be3d0e
Revises: a6e4b91c2d73
Create Date: 2026-07-28 17:19:34.916365
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "33ac84be3d0e"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "a6e4b91c2d73"

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
    """Create the conversation tool-execution audit table."""

    op.create_table(
        "conversation_tool_executions",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "assistant_message_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "execution_order",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "attempt_phase",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "tool_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "validated_arguments_json",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "failure_category",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "duration_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "execution_order >= 1",
            name=op.f(
                "ck_conversation_tool_executions_"
                "execution_order_positive"
            ),
        ),
        sa.CheckConstraint(
            (
                "attempt_phase IN "
                "('action_selection', 'action_repair')"
            ),
            name=op.f(
                "ck_conversation_tool_executions_"
                "attempt_phase"
            ),
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('succeeded', 'execution_failed', "
                "'arguments_rejected', 'unknown_tool')"
            ),
            name=op.f(
                "ck_conversation_tool_executions_status"
            ),
        ),
        sa.CheckConstraint(
            (
                "duration_ms IS NULL "
                "OR duration_ms >= 0"
            ),
            name=op.f(
                "ck_conversation_tool_executions_"
                "duration_ms_nonnegative"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            ["conversation_messages.id"],
            name=op.f(
                "fk_conversation_tool_executions_"
                "assistant_message_id_conversation_messages"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f(
                "fk_conversation_tool_executions_"
                "organization_id_organizations"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["conversation_sessions.id"],
            name=op.f(
                "fk_conversation_tool_executions_"
                "session_id_conversation_sessions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_conversation_tool_executions"
            ),
        ),
        sa.UniqueConstraint(
            "assistant_message_id",
            "execution_order",
            name=op.f(
                "uq_conversation_tool_executions_"
                "assistant_message_id"
            ),
        ),
    )

    op.create_index(
        "ix_conversation_tool_executions_session_created",
        "conversation_tool_executions",
        [
            "session_id",
            "created_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_conversation_tool_executions_org_created",
        "conversation_tool_executions",
        [
            "organization_id",
            "created_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Remove the conversation tool-execution audit table."""

    op.drop_index(
        "ix_conversation_tool_executions_org_created",
        table_name="conversation_tool_executions",
    )

    op.drop_index(
        "ix_conversation_tool_executions_session_created",
        table_name="conversation_tool_executions",
    )

    op.drop_table(
        "conversation_tool_executions"
    )