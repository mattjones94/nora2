from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.llm.capabilities import ModelCapabilities


ModelAdapterType = Literal[
    "development",
    "openai_compatible",
    "anthropic",
    "litert_lm",
]

ModelToolMode = Literal[
    "structured_json",
    "native",
]

ModelReasoningEffort = Literal[
    "none",
    "low",
    "medium",
    "high",
]


class ModelProfile(BaseModel):
    """
    Configuration describing one model connection available to NORA.

    The profile contains configuration only. API keys and other secrets
    are referenced by environment-variable name rather than stored here.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    profile_key: str = Field(
        min_length=1,
        max_length=100,
    )

    display_name: str = Field(
        min_length=1,
        max_length=200,
    )

    adapter_type: ModelAdapterType

    provider_name: str = Field(
        min_length=1,
        max_length=100,
    )

    model_name: str = Field(
        min_length=1,
        max_length=200,
    )

    base_url: str | None = Field(
        default=None,
        max_length=2048,
    )

    credential_env_var: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    tool_mode: ModelToolMode = "structured_json"

    reasoning_effort: ModelReasoningEffort | None = None

    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )

    maximum_output_tokens: int = Field(
        default=512,
        ge=1,
    )

    request_timeout_seconds: float = Field(
        default=120.0,
        gt=0.0,
        le=600.0,
    )

    capabilities: ModelCapabilities

    enabled: bool = True

    @model_validator(mode="after")
    def validate_adapter_configuration(
        self,
    ) -> "ModelProfile":
        if (
            self.adapter_type == "openai_compatible"
            and not self.base_url
        ):
            raise ValueError(
                "base_url is required for an "
                "openai_compatible profile"
            )

        if (
            self.tool_mode == "native"
            and not self.capabilities.supports_native_tools
        ):
            raise ValueError(
                "tool_mode cannot be native when native tools "
                "are not supported"
            )

        if (
            self.reasoning_effort is not None
            and not self.capabilities.supports_reasoning_effort
        ):
            raise ValueError(
                "reasoning_effort cannot be configured when "
                "the profile does not support it"
            )

        return self


def create_development_model_profile() -> ModelProfile:
    """Return the deterministic profile used during development."""

    return ModelProfile(
        profile_key="development-default",
        display_name="Development Test Model",
        adapter_type="development",
        provider_name="development",
        model_name="deterministic-test-client",
        base_url=None,
        credential_env_var=None,
        tool_mode="structured_json",
        reasoning_effort=None,
        temperature=0.0,
        maximum_output_tokens=512,
        request_timeout_seconds=120.0,
        capabilities=ModelCapabilities(
            supports_native_tools=False,
            supports_structured_output=True,
            accepts_response_format_json_object=False,
            supports_reasoning_effort=False,
            supports_streaming=False,
            supports_system_messages=True,
            supports_multiple_tool_calls=False,
            supports_vision=False,
            output_token_parameter="none",
            maximum_context_tokens=8192,
            maximum_output_tokens=512,
        ),
        enabled=True,
    )


def create_ollama_qwen3_1_7b_profile() -> ModelProfile:
    """Return the local Ollama Qwen3 demonstration profile."""

    return ModelProfile(
        profile_key="ollama-qwen3-1.7b",
        display_name="Local Ollama Qwen3 1.7B",
        adapter_type="openai_compatible",
        provider_name="ollama",
        model_name="qwen3:1.7b",
        base_url=(
            "http://host.docker.internal:11434/v1"
        ),
        credential_env_var=None,
        tool_mode="structured_json",
        reasoning_effort="none",
        temperature=0.0,
        maximum_output_tokens=512,
        request_timeout_seconds=180.0,
        capabilities=ModelCapabilities(
            supports_native_tools=False,
            supports_structured_output=True,
            accepts_response_format_json_object=True,
            supports_reasoning_effort=True,
            supports_streaming=False,
            supports_system_messages=True,
            supports_multiple_tool_calls=False,
            supports_vision=False,
            output_token_parameter="max_tokens",
            maximum_context_tokens=None,
            maximum_output_tokens=512,
        ),
        enabled=True,
    )