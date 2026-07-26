"""create conversation tables

Revision ID: 9f4c2d7a6b11
Revises: d3a71f42c8e6
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f4c2d7a6b11"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "d3a71f42c8e6"

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
    """Create conversation session, message, and metric tables."""

    op.create_table(
        "conversation_sessions",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "public_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.String(length=50),
            server_default=sa.text("'web'"),
            nullable=False,
        ),
        sa.Column(
            "model_profile_key",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "close_reason",
            sa.String(length=100),
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
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('active', 'closed', 'expired', "
                "'abandoned', 'error')"
            ),
            name=op.f(
                "ck_conversation_sessions_status"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f(
                "fk_conversation_sessions_"
                "organization_id_organizations"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_conversation_sessions"
            ),
        ),
        sa.UniqueConstraint(
            "public_id",
            name=op.f(
                "uq_conversation_sessions_public_id"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_conversation_sessions_organization_id"
        ),
        "conversation_sessions",
        ["organization_id"],
        unique=False,
    )

    op.create_index(
        "ix_conversation_sessions_org_status_expires",
        "conversation_sessions",
        [
            "organization_id",
            "status",
            "expires_at",
        ],
        unique=False,
    )

    op.create_table(
        "conversation_messages",
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
            "sequence_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "message_type",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text(
                "'completed'"
            ),
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "tool_name",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "tool_arguments_json",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "tool_result_json",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "provider_name",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "model_name",
            sa.String(length=200),
            nullable=True,
        ),
        sa.Column(
            "input_tokens",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "output_tokens",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "request_started_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "model_started_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "first_token_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "time_to_first_token_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "model_time_to_first_token_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "total_response_time_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "is_user_visible",
            sa.Boolean(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "role IN "
                "('system', 'user', 'assistant', 'tool')"
            ),
            name=op.f(
                "ck_conversation_messages_role"
            ),
        ),
        sa.CheckConstraint(
            (
                "message_type IN "
                "('user_message', 'assistant_message', "
                "'tool_call', 'tool_result', "
                "'system_instruction', 'error')"
            ),
            name=op.f(
                "ck_conversation_messages_message_type"
            ),
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('pending', 'streaming', "
                "'completed', 'failed')"
            ),
            name=op.f(
                "ck_conversation_messages_status"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["conversation_sessions.id"],
            name=op.f(
                "fk_conversation_messages_"
                "session_id_conversation_sessions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_conversation_messages"
            ),
        ),
        sa.UniqueConstraint(
            "session_id",
            "sequence_number",
            name=op.f(
                "uq_conversation_messages_session_id"
            ),
        ),
    )

    op.create_index(
        "ix_conversation_messages_session_created",
        "conversation_messages",
        [
            "session_id",
            "created_at",
        ],
        unique=False,
    )

    op.create_table(
        "conversation_session_metrics",
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
            "organization_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "user_message_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "assistant_message_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "tool_call_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "successful_tool_call_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "failed_tool_call_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "error_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "duration_seconds",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "average_time_to_first_token_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "maximum_time_to_first_token_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "average_model_time_to_first_token_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "average_total_response_time_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "maximum_total_response_time_ms",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "total_input_tokens",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "total_output_tokens",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "completion_status",
            sa.String(length=30),
            server_default=sa.text(
                "'in_progress'"
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "completion_status IN "
                "('in_progress', 'completed', "
                "'abandoned', 'expired', 'error')"
            ),
            name=op.f(
                "ck_conversation_session_metrics_"
                "completion_status"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f(
                "fk_conversation_session_metrics_"
                "organization_id_organizations"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["conversation_sessions.id"],
            name=op.f(
                "fk_conversation_session_metrics_"
                "session_id_conversation_sessions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_conversation_session_metrics"
            ),
        ),
        sa.UniqueConstraint(
            "session_id",
            name=op.f(
                "uq_conversation_session_metrics_session_id"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_conversation_session_metrics_organization_id"
        ),
        "conversation_session_metrics",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove conversation metric, message, and session tables."""

    op.drop_index(
        op.f(
            "ix_conversation_session_metrics_organization_id"
        ),
        table_name="conversation_session_metrics",
    )

    op.drop_table(
        "conversation_session_metrics"
    )

    op.drop_index(
        "ix_conversation_messages_session_created",
        table_name="conversation_messages",
    )

    op.drop_table(
        "conversation_messages"
    )

    op.drop_index(
        "ix_conversation_sessions_org_status_expires",
        table_name="conversation_sessions",
    )

    op.drop_index(
        op.f(
            "ix_conversation_sessions_organization_id"
        ),
        table_name="conversation_sessions",
    )

    op.drop_table(
        "conversation_sessions"
    )