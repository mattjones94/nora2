class DepartmentDetailError(Exception):
    """Base exception for department-detail operations."""


class OrganizationNotFoundError(
    DepartmentDetailError
):
    """The requested organization does not exist."""


class DepartmentNotFoundError(
    DepartmentDetailError
):
    """The requested department does not exist."""


class DepartmentDetailNotFoundError(
    DepartmentDetailError
):
    """The requested department-details record does not exist."""


class DepartmentDetailConflictError(
    DepartmentDetailError
):
    """A department-details record could not be created uniquely."""