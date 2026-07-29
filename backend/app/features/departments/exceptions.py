class DepartmentError(Exception):
    """Base exception for department operations."""


class OrganizationNotFoundError(DepartmentError):
    """The requested parent organization does not exist."""


class OrganizationInactiveError(DepartmentError):
    """The requested parent organization is inactive."""


class DepartmentNotFoundError(DepartmentError):
    """The requested department does not exist."""


class DepartmentSlugConflictError(DepartmentError):
    """The department slug is already used by the organization."""