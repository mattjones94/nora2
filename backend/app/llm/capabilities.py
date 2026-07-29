from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


ModelOutputTokenParameter = Literal[
    "max_tokens",
    "max_completion_tokens",
    "none",
]


class ModelCapabilities(BaseModel):
    """Features supported by a configured model and its adapter."""

    model_config = ConfigDict(
        extra="forbid",
    )

    supports_native_tools: bool = False

    supports_structured_output: bool = False

    accepts_response_format_json_object: bool = False

    supports_reasoning_effort: bool = False

    supports_streaming: bool = False

    supports_system_messages: bool = True

    supports_multiple_tool_calls: bool = False

    supports_vision: bool = False

    output_token_parameter: ModelOutputTokenParameter = (
        "max_tokens"
    )

    maximum_context_tokens: int | None = Field(
        default=None,
        ge=1,
    )

    maximum_output_tokens: int | None = Field(
        default=None,
        ge=1,
    )