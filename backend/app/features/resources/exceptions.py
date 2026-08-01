class ResourceError(Exception):
    """Base exception for resource operations."""


class ResourceValidationError(ResourceError):
    """The supplied resource data violates an application rule."""


class OrganizationNotFoundError(ResourceError):
    """The requested parent organization does not exist."""


class OrganizationInactiveError(ResourceError):
    """The requested parent organization is inactive."""


class DepartmentNotFoundError(ResourceError):
    """The requested department does not exist in the organization."""


class DepartmentInactiveError(ResourceError):
    """The selected department is inactive."""


class ResourceNotFoundError(ResourceError):
    """The requested organization resource does not exist."""


class ResourceSlugConflictError(ResourceError):
    """The resource slug is already used by the organization."""


class ResourcePublicationValidationError(
    ResourceValidationError
):
    """The resource does not contain enough data to be published."""