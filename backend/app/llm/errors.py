class NoraLlmError(Exception):
    """Base error for NORA's model-runtime integration."""


class ModelProtocolError(NoraLlmError):
    """Base error for model output that violates NORA's protocol."""

    repairable: bool = True

    def __init__(
        self,
        message: str,
        *,
        attempted_tool_call_count: int = 0,
    ) -> None:
        self.attempted_tool_call_count = (
            attempted_tool_call_count
        )

        super().__init__(
            message
        )


class ModelActionError(ModelProtocolError):
    """Base error for invalid model action output."""


class InvalidModelActionError(ModelActionError):
    """
    Compatibility base for malformed or structurally invalid actions.

    Existing callers may continue catching this class while more
    specific subclasses identify the exact protocol failure.
    """


class MalformedActionJsonError(
    InvalidModelActionError
):
    """Raised when action-selection output is not valid JSON."""

    def __init__(
        self,
        detail: str,
    ) -> None:
        super().__init__(
            f"Model action output was not valid JSON: {detail}"
        )


class InvalidActionEnvelopeError(
    InvalidModelActionError
):
    """Raised when valid JSON does not match the action contract."""

    def __init__(
        self,
        detail: str,
    ) -> None:
        super().__init__(
            f"Model action output did not match the required "
            f"action contract: {detail}"
        )


class UnknownToolError(ModelProtocolError):
    """Raised when the model requests an unregistered tool."""

    def __init__(
        self,
        tool_name: str,
    ) -> None:
        self.tool_name = tool_name

        super().__init__(
            f"Model requested the unregistered tool "
            f"'{tool_name}'.",
            attempted_tool_call_count=1,
        )


class InvalidToolArgumentsError(
    ModelProtocolError
):
    """Raised when a tool call contains invalid arguments."""

    def __init__(
        self,
        *,
        tool_name: str,
        detail: str,
    ) -> None:
        self.tool_name = tool_name
        self.detail = detail

        super().__init__(
            f"Model supplied invalid arguments for tool "
            f"'{tool_name}': {detail}",
            attempted_tool_call_count=1,
        )


class UnsupportedToolCallCountError(
    ModelProtocolError
):
    """Raised when a response requests an unsupported call count."""

    def __init__(
        self,
        call_count: int,
    ) -> None:
        self.call_count = call_count

        super().__init__(
            "The current NORA protocol supports exactly one "
            f"tool call, but the model returned {call_count}.",
            attempted_tool_call_count=max(
                0,
                call_count,
            ),
        )


class UnexpectedFollowUpToolCallError(
    ModelProtocolError
):
    """Raised when final synthesis unexpectedly requests another tool."""

    def __init__(
        self,
        call_count: int = 1,
    ) -> None:
        self.call_count = call_count

        super().__init__(
            "The model requested another tool during final "
            "tool-result synthesis.",
            attempted_tool_call_count=max(
                0,
                call_count,
            ),
        )