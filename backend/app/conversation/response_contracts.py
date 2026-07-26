from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class ConversationTurnResult:
    """
    Result produced after the orchestrator completes one user turn.

    The result includes the user-facing response together with model
    usage and tool-execution metadata needed by message persistence
    and conversation analytics.
    """

    message: str

    provider_name: str | None = None
    model_name: str | None = None

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    tool_call_count: int = 0
    successful_tool_call_count: int = 0