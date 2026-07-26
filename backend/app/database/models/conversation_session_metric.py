from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.conversation_session import (
        ConversationSession,
    )
    from app.database.models.organization import Organization


class ConversationSessionMetric(Base):
    """Aggregated performance and usage metrics for one conversation."""

    __tablename__ = "conversation_session_metrics"

    __table_args__ = (
        UniqueConstraint(
            "session_id",
        ),
        CheckConstraint(
            (
                "completion_status IN "
                "('in_progress', 'completed', 'abandoned', "
                "'expired', 'error')"
            ),
            name="completion_status",
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

    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "organizations.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    user_message_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    assistant_message_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    tool_call_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    successful_tool_call_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    failed_tool_call_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    duration_seconds: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    average_time_to_first_token_ms: Mapped[
        int | None
    ] = mapped_column(
        BigInteger,
        nullable=True,
    )

    maximum_time_to_first_token_ms: Mapped[
        int | None
    ] = mapped_column(
        BigInteger,
        nullable=True,
    )

    average_model_time_to_first_token_ms: Mapped[
        int | None
    ] = mapped_column(
        BigInteger,
        nullable=True,
    )

    average_total_response_time_ms: Mapped[
        int | None
    ] = mapped_column(
        BigInteger,
        nullable=True,
    )

    maximum_total_response_time_ms: Mapped[
        int | None
    ] = mapped_column(
        BigInteger,
        nullable=True,
    )

    total_input_tokens: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    total_output_tokens: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    completion_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="in_progress",
        server_default="in_progress",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    session: Mapped["ConversationSession"] = relationship(
        back_populates="metrics",
    )

    organization: Mapped["Organization"] = relationship(
        back_populates="conversation_session_metrics",
    )