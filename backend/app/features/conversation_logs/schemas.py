from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ConversationSessionStatus = Literal[
    "active",
    "closed",
    "expired",
    "abandoned",
    "error",
]

ConversationCompletionStatus = Literal[
    "in_progress",
    "completed",
    "abandoned",
    "expired",
    "error",
]

ConversationMessageRole = Literal[
    "system",
    "user",
    "assistant",
    "tool",
]

ConversationMessageType = Literal[
    "user_message",
    "assistant_message",
    "tool_call",
    "tool_result",
    "system_instruction",
    "error",
]

ConversationMessageStatus = Literal[
    "pending",
    "streaming",
    "completed",
    "failed",
]

ConversationToolAttemptPhase = Literal[
    "action_selection",
    "action_repair",
]

ConversationToolExecutionStatus = Literal[
    "succeeded",
    "execution_failed",
    "arguments_rejected",
    "unknown_tool",
]


class ConversationLogSessionResponse(BaseModel):
    """Administrative session details for one conversation."""

    session_id: str
    organization_id: int

    status: ConversationSessionStatus
    channel: str
    model_profile_key: str

    started_at: datetime
    last_activity_at: datetime
    expires_at: datetime

    ended_at: datetime | None
    close_reason: str | None

    created_at: datetime
    updated_at: datetime


class ConversationLogMetricsResponse(BaseModel):
    """Stored aggregate metrics for one conversation."""

    user_message_count: int
    assistant_message_count: int

    tool_call_count: int
    successful_tool_call_count: int
    failed_tool_call_count: int

    error_count: int
    duration_seconds: int | None

    average_time_to_first_token_ms: int | None
    maximum_time_to_first_token_ms: int | None

    average_model_time_to_first_token_ms: int | None

    average_total_response_time_ms: int | None
    maximum_total_response_time_ms: int | None

    total_input_tokens: int
    total_output_tokens: int

    completion_status: ConversationCompletionStatus

    created_at: datetime
    updated_at: datetime


class ConversationLogToolExecutionResponse(BaseModel):
    """One audited tool attempt associated with an assistant message."""

    execution_order: int
    attempt_phase: ConversationToolAttemptPhase

    tool_name: str
    validated_arguments: dict[str, Any] | None

    status: ConversationToolExecutionStatus
    failure_category: str | None

    duration_ms: int | None
    created_at: datetime


class ConversationLogMessageResponse(BaseModel):
    """One ordered conversation message returned for admin review."""

    message_id: int
    sequence_number: int

    role: ConversationMessageRole
    message_type: ConversationMessageType
    status: ConversationMessageStatus

    content: str | None

    tool_name: str | None
    tool_arguments: dict[str, Any] | None
    tool_result: dict[str, Any] | None

    provider_name: str | None
    model_name: str | None

    input_tokens: int | None
    output_tokens: int | None

    tool_call_count: int
    successful_tool_call_count: int

    request_started_at: datetime | None
    model_started_at: datetime | None
    first_token_at: datetime | None
    completed_at: datetime | None

    time_to_first_token_ms: int | None
    model_time_to_first_token_ms: int | None
    total_response_time_ms: int | None

    is_user_visible: bool

    created_at: datetime
    updated_at: datetime

    tool_executions: list[
        ConversationLogToolExecutionResponse
    ] = Field(
        default_factory=list,
    )


class ConversationLogSummaryResponse(BaseModel):
    """
    Lightweight conversation data used by the organization conversation
    list.

    Message content and individual tool executions are intentionally
    excluded.
    """

    session_id: str
    organization_id: int

    status: ConversationSessionStatus
    channel: str
    model_profile_key: str

    started_at: datetime
    last_activity_at: datetime
    expires_at: datetime

    ended_at: datetime | None
    close_reason: str | None

    message_count: int
    user_message_count: int
    assistant_message_count: int

    tool_call_count: int
    successful_tool_call_count: int
    failed_tool_call_count: int

    error_count: int
    duration_seconds: int | None

    average_total_response_time_ms: int | None
    maximum_total_response_time_ms: int | None

    total_input_tokens: int
    total_output_tokens: int

    completion_status: ConversationCompletionStatus


class ConversationLogListResponse(BaseModel):
    """Paginated conversations belonging to one organization."""

    items: list[
        ConversationLogSummaryResponse
    ] = Field(
        default_factory=list,
    )

    total: int
    limit: int
    offset: int


class ConversationLogDetailResponse(BaseModel):
    """Complete administrative log for one selected conversation."""

    session: ConversationLogSessionResponse
    metrics: ConversationLogMetricsResponse

    messages: list[
        ConversationLogMessageResponse
    ] = Field(
        default_factory=list,
    )



class ConversationAnalyticsSessionCountsResponse(
    BaseModel
):
    """Organization conversation totals grouped by session status."""

    total: int

    active: int
    closed: int
    expired: int
    abandoned: int
    error: int


class ConversationAnalyticsMessageTotalsResponse(
    BaseModel
):
    """Aggregated message totals across matching conversations."""

    total: int
    user: int
    assistant: int

    recorded_error_count: int


class ConversationAnalyticsTokenTotalsResponse(
    BaseModel
):
    """Aggregated model-token usage."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class ConversationAnalyticsToolTotalsResponse(
    BaseModel
):
    """Aggregated tool-call results."""

    tool_call_count: int
    successful_tool_call_count: int
    failed_tool_call_count: int

    success_rate_percent: float | None


class ConversationAnalyticsPerformanceResponse(
    BaseModel
):
    """Aggregated timing and conversation-duration statistics."""

    average_duration_seconds: float | None

    average_total_response_time_ms: int | None
    maximum_total_response_time_ms: int | None

    average_time_to_first_token_ms: int | None
    maximum_time_to_first_token_ms: int | None

    average_model_time_to_first_token_ms: int | None


class ConversationAnalyticsToolUsageResponse(
    BaseModel
):
    """Aggregated execution statistics for one tool."""

    tool_name: str

    execution_count: int
    succeeded_count: int

    execution_failed_count: int
    arguments_rejected_count: int
    unknown_tool_count: int

    success_rate_percent: float | None

    average_duration_ms: float | None
    maximum_duration_ms: int | None


class ConversationAnalyticsSummaryResponse(
    BaseModel
):
    """Organization-wide conversation analytics summary."""

    organization_id: int

    status_filter: ConversationSessionStatus | None
    started_from: datetime | None
    started_to: datetime | None

    sessions: ConversationAnalyticsSessionCountsResponse

    messages: ConversationAnalyticsMessageTotalsResponse

    tokens: ConversationAnalyticsTokenTotalsResponse

    tools: ConversationAnalyticsToolTotalsResponse

    performance: ConversationAnalyticsPerformanceResponse

    tool_usage: list[
        ConversationAnalyticsToolUsageResponse
    ] = Field(
        default_factory=list,
    )



    