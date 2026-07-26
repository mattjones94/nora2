from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.conversation_session import (
        ConversationSession,
    )


class ConversationMessage(Base):
    """One stored message or internal activity within a conversation."""

    __tablename__ = "conversation_messages"

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sequence_number",
        ),
        CheckConstraint(
            "role IN ('system', 'user', 'assistant', 'tool')",
            name="role",
        ),
        CheckConstraint(
            (
                "message_type IN "
                "('user_message', 'assistant_message', "
                "'tool_call', 'tool_result', "
                "'system_instruction', 'error')"
            ),
            name="message_type",
        ),
        CheckConstraint(
            (
                "status IN "
                "('pending', 'streaming', 'completed', 'failed')"
            ),
            name="status",
        ),
        Index(
            "ix_conversation_messages_session_created",
            "session_id",
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

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    message_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="completed",
        server_default="completed",
    )

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tool_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    tool_arguments_json: Mapped[
        dict[str, Any] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    tool_result_json: Mapped[
        dict[str, Any] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    provider_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    input_tokens: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    output_tokens: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    request_started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    model_started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    first_token_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    time_to_first_token_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    model_time_to_first_token_ms: Mapped[
        int | None
    ] = mapped_column(
        BigInteger,
        nullable=True,
    )

    total_response_time_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    is_user_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
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
        back_populates="messages",
    )