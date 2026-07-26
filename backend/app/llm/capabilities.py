from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ModelCapabilities(BaseModel):
    """Features supported by a configured model and its adapter."""

    model_config = ConfigDict(
        extra="forbid",
    )

    supports_native_tools: bool = False

    supports_structured_output: bool = False

    supports_streaming: bool = False

    supports_system_messages: bool = True

    supports_multiple_tool_calls: bool = False

    supports_vision: bool = False

    maximum_context_tokens: int | None = Field(
        default=None,
        ge=1,
    )

    maximum_output_tokens: int | None = Field(
        default=None,
        ge=1,
    )