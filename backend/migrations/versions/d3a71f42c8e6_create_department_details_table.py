"""create department details table

Revision ID: d3a71f42c8e6
Revises: b56aaea891ed
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3a71f42c8e6"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "b56aaea891ed"

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
    """Create the department_details table."""

    op.create_table(
        "department_details",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "primary_contact_name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "primary_contact_title",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "email",
            sa.String(length=320),
            nullable=True,
        ),
        sa.Column(
            "phone",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "location",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "office_hours",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "website_url",
            sa.String(length=2048),
            nullable=True,
        ),
        sa.Column(
            "additional_information",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name=op.f("ck_department_details_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f(
                "fk_department_details_organization_id_organizations"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f(
                "fk_department_details_department_id_departments"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_department_details"),
        ),
        sa.UniqueConstraint(
            "department_id",
            name=op.f(
                "uq_department_details_department_id"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_department_details_organization_id"
        ),
        "department_details",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the department_details table."""

    op.drop_index(
        op.f(
            "ix_department_details_organization_id"
        ),
        table_name="department_details",
    )

    op.drop_table(
        "department_details"
    )