from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


ModelRole = Literal[
    "system",
    "user",
    "assistant",
    "tool",
]

ModelResponseFormat = Literal[
    "text",
    "json_object",
]

ModelFinishReason = Literal[
    "stop",
    "tool_call",
    "length",
    "content_filter",
    "error",
    "unknown",
]


class ModelMessage(BaseModel):
    """One provider-neutral message sent to a model."""

    model_config = ConfigDict(
        extra="forbid",
    )

    role: ModelRole

    content: str | None = None

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    tool_call_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )


class ModelToolDefinition(BaseModel):
    """One NORA tool made available to a model."""

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    description: str = Field(
        min_length=1,
        max_length=2000,
    )

    input_schema: dict[str, Any]


class ModelToolCall(BaseModel):
    """One normalized tool request returned by a model."""

    model_config = ConfigDict(
        extra="forbid",
    )

    call_id: str = Field(
        min_length=1,
        max_length=200,
    )

    tool_name: str = Field(
        min_length=1,
        max_length=100,
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict,
    )


class ModelRequest(BaseModel):
    """Provider-neutral request sent from NORA to a model adapter."""

    model_config = ConfigDict(
        extra="forbid",
    )

    messages: list[ModelMessage] = Field(
        min_length=1,
    )

    tools: list[ModelToolDefinition] = Field(
        default_factory=list,
    )

    response_format: ModelResponseFormat = "text"

    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )

    max_output_tokens: int = Field(
        default=512,
        ge=1,
    )

    stream: bool = False

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


class ModelUsage(BaseModel):
    """Normalized token-usage information when supplied by a provider."""

    model_config = ConfigDict(
        extra="forbid",
    )

    input_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    output_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    total_tokens: int | None = Field(
        default=None,
        ge=0,
    )


class ModelResponse(BaseModel):
    """Provider-neutral response returned by a model adapter."""

    model_config = ConfigDict(
        extra="forbid",
    )

    text: str | None = None

    tool_calls: list[ModelToolCall] = Field(
        default_factory=list,
    )

    finish_reason: ModelFinishReason = "unknown"

    usage: ModelUsage | None = None

    provider_name: str | None = None

    model_name: str | None = None

    provider_metadata: dict[str, Any] = Field(
        default_factory=dict,
    )

    raw_response: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_response_content(self) -> "ModelResponse":
        has_text = bool(
            self.text
            and self.text.strip()
        )

        if not has_text and not self.tool_calls:
            raise ValueError(
                "A model response must contain text or at least one tool call."
            )

        return self