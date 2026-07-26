from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.conversation_session import (
        ConversationSession,
    )
    from app.database.models.conversation_session_metric import (
        ConversationSessionMetric,
    )
    from app.database.models.department import Department
    from app.database.models.department_detail import DepartmentDetail


class Organization(Base):
    """An organization whose information is managed by NORA."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="active",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    departments: Mapped[list["Department"]] = relationship(
    back_populates="organization",
    )

    department_details: Mapped[list["DepartmentDetail"]] = relationship(
    back_populates="organization",
    )

    conversation_sessions: Mapped[
        list["ConversationSession"]
    ] = relationship(
        back_populates="organization",
    )

    conversation_session_metrics: Mapped[
        list["ConversationSessionMetric"]
    ] = relationship(
        back_populates="organization",
    )