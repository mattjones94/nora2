from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.conversation_message import (
        ConversationMessage,
    )
    from app.database.models.conversation_session_metric import (
        ConversationSessionMetric,
    )
    from app.database.models.organization import Organization


class ConversationSession(Base):
    """One public conversation within a NORA organization."""

    __tablename__ = "conversation_sessions"

    __table_args__ = (
        UniqueConstraint(
            "public_id",
        ),
        CheckConstraint(
            (
                "status IN "
                "('active', 'closed', 'expired', "
                "'abandoned', 'error')"
            ),
            name="status",
        ),
        Index(
            "ix_conversation_sessions_org_status_expires",
            "organization_id",
            "status",
            "expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    public_id: Mapped[str] = mapped_column(
        String(36),
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

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )

    channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="web",
        server_default="web",
    )

    model_profile_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    close_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
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

    organization: Mapped["Organization"] = relationship(
        back_populates="conversation_sessions",
    )

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConversationMessage.sequence_number",
    )

    metrics: Mapped["ConversationSessionMetric | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )