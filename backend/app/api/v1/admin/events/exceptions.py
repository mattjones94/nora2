class EventServiceError(Exception):
    """Base exception for event application errors."""


class OrganizationNotFoundError(EventServiceError):
    """Raised when the requested organization does not exist."""

    def __init__(self) -> None:
        super().__init__("Organization not found.")


class OrganizationInactiveError(EventServiceError):
    """Raised when the requested organization is inactive."""

    def __init__(self) -> None:
        super().__init__("The organization is inactive.")


class DepartmentNotFoundError(EventServiceError):
    """Raised when the department is not part of the organization."""

    def __init__(self) -> None:
        super().__init__(
            "Department not found within the requested organization."
        )


class DepartmentInactiveError(EventServiceError):
    """Raised when the requested department is inactive."""

    def __init__(self) -> None:
        super().__init__("The department is inactive.")


class EventNotFoundError(EventServiceError):
    """Raised when the requested event does not exist."""

    def __init__(self) -> None:
        super().__init__(
            "Event not found within the requested department."
        )