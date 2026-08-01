from dataclasses import dataclass
from typing import Any, Literal


ToolExecutionAttemptPhase = Literal[
    "action_selection",
    "action_repair",
]

ToolExecutionStatus = Literal[
    "succeeded",
    "execution_failed",
    "arguments_rejected",
    "unknown_tool",
]


@dataclass(
    frozen=True,
    slots=True,
)
class ConversationToolExecutionRecord:
    """
    One bounded audit record for a counted tool attempt.

    Session, organization, and assistant-message identifiers are added
    later by the persistence layer from trusted application context.
    """

    execution_order: int
    attempt_phase: ToolExecutionAttemptPhase

    tool_name: str

    validated_arguments_json: dict[str, Any] | None

    status: ToolExecutionStatus

    failure_category: str | None = None
    duration_ms: int | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class ConversationToolResultRecord:
    """
    One validated successful tool result retained for persistence.

    The record contains only provider-neutral registered-tool data.
    Session, organization, and conversation-message identifiers are
    added later by the persistence layer from trusted application
    context.
    """

    execution_order: int

    tool_name: str

    validated_arguments_json: dict[str, Any]

    result_json: dict[str, Any]

@dataclass(
    frozen=True,
    slots=True,
)
class ConversationToolContextRecord:
    """
    One verified historical tool result available to a future turn.

    The sequence number preserves its position in the conversation.
    Organization scope remains controlled separately by trusted
    application context and is never derived from this record.
    """

    sequence_number: int

    tool_name: str

    validated_arguments_json: dict[str, Any]

    result_json: dict[str, Any]


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

    tool_executions: tuple[
        ConversationToolExecutionRecord,
        ...
    ] = ()

    tool_results: tuple[
        ConversationToolResultRecord,
        ...
    ] = ()


@dataclass(
    frozen=True,
    slots=True,
)
class ConversationStreamTextDelta:
    """One ordered fragment of public assistant text."""

    content: str


@dataclass(
    frozen=True,
    slots=True,
)
class ConversationStreamCompleted:
    """The completed conversation result after streaming finishes."""

    result: ConversationTurnResult


ConversationStreamEvent = (
    ConversationStreamTextDelta
    | ConversationStreamCompleted
)