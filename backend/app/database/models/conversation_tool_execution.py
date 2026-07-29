from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ConversationToolExecution(Base):
    """One audited tool attempt associated with an assistant turn."""

    __tablename__ = "conversation_tool_executions"

    __table_args__ = (
        UniqueConstraint(
            "assistant_message_id",
            "execution_order",
        ),
        CheckConstraint(
            "execution_order >= 1",
            name="execution_order_positive",
        ),
        CheckConstraint(
            (
                "attempt_phase IN "
                "('action_selection', 'action_repair')"
            ),
            name="attempt_phase",
        ),
        CheckConstraint(
            (
                "status IN "
                "('succeeded', 'execution_failed', "
                "'arguments_rejected', 'unknown_tool')"
            ),
            name="status",
        ),
        CheckConstraint(
            (
                "duration_ms IS NULL "
                "OR duration_ms >= 0"
            ),
            name="duration_ms_nonnegative",
        ),
        Index(
            "ix_conversation_tool_executions_session_created",
            "session_id",
            "created_at",
        ),
        Index(
            "ix_conversation_tool_executions_org_created",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "conversation_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    assistant_message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "conversation_messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "organizations.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    execution_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    attempt_phase: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    validated_arguments_json: Mapped[
        dict[str, Any] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    failure_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )