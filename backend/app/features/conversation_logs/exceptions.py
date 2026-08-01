class ConversationLogError(Exception):
    """Base error raised while reading conversation logs."""


class OrganizationNotFoundError(
    ConversationLogError
):
    """Raised when the requested organization does not exist."""

    def __init__(self) -> None:
        super().__init__(
            "Organization not found."
        )


class ConversationLogNotFoundError(
    ConversationLogError
):
    """Raised when an organization-scoped conversation is absent."""

    def __init__(self) -> None:
        super().__init__(
            "Conversation log not found within the requested "
            "organization."
        )


class InvalidConversationLogSessionIdError(
    ConversationLogError
):
    """Raised when a public conversation ID is not a valid UUID."""

    def __init__(self) -> None:
        super().__init__(
            "The supplied conversation session ID is invalid."
        )


class ConversationLogMetricsNotFoundError(
    ConversationLogError
):
    """Raised when a conversation is missing its metrics record."""

    def __init__(
        self,
        *,
        public_id: str,
    ) -> None:
        super().__init__(
            "The conversation metrics record could not be found "
            f"for session '{public_id}'."
        )


class InvalidConversationLogDateRangeError(
    ConversationLogError
):
    """Raised when the end of a date range precedes its start."""

    def __init__(self) -> None:
        super().__init__(
            "started_to must be equal to or later than "
            "started_from."
        )