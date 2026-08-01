from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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
    from app.database.models.department import Department
    from app.database.models.organization import Organization


class Resource(Base):
    """
    One published or draft information resource owned by an organization.

    A null department_id makes the resource organization-wide.
    """

    __tablename__ = "resources"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
        ),
        CheckConstraint(
            (
                "resource_type IN "
                "('document', 'external_link', 'form', "
                "'guide', 'website', 'information')"
            ),
            name="resource_type",
        ),
        CheckConstraint(
            (
                "status IN "
                "('draft', 'published', 'inactive')"
            ),
            name="status",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="display_order_nonnegative",
        ),
        Index(
            "ix_resources_org_department_status",
            "organization_id",
            "department_id",
            "status",
        ),
        Index(
            "ix_resources_org_status_type",
            "organization_id",
            "status",
            "resource_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
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

    department_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "departments.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    content_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    aliases_json: Mapped[
        list[str] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    topics_json: Mapped[
        list[str] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    when_to_use: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    when_not_to_use: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
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
        back_populates="resources",
    )

    department: Mapped[
        "Department | None"
    ] = relationship(
        back_populates="resources",
    )