from collections.abc import Callable

from app.llm.adapters.development import (
    DevelopmentModelClient,
)
from app.llm.adapters.openai_compatible import (
    OpenAICompatibleModelClient,
)
from app.llm.model_profiles import ModelProfile
from app.llm.runtime import ModelClient


class ModelClientFactoryError(Exception):
    """Base error raised while constructing a model client."""


class DisabledModelProfileError(ModelClientFactoryError):
    """Raised when a disabled profile is selected."""

    def __init__(
        self,
        profile_key: str,
    ) -> None:
        super().__init__(
            f"Model profile '{profile_key}' is disabled."
        )


class UnsupportedModelAdapterError(
    ModelClientFactoryError
):
    """Raised when no client builder exists for an adapter."""

    def __init__(
        self,
        adapter_type: str,
    ) -> None:
        super().__init__(
            f"Model adapter '{adapter_type}' is not supported."
        )


ModelClientBuilder = Callable[
    [ModelProfile],
    ModelClient,
]


def _build_development_client(
    profile: ModelProfile,
) -> ModelClient:
    """Build the deterministic development client."""

    return DevelopmentModelClient(
        profile=profile,
    )


def _build_openai_compatible_client(
    profile: ModelProfile,
) -> ModelClient:
    """Build an OpenAI-compatible HTTP model client."""

    return OpenAICompatibleModelClient(
        profile=profile,
    )


_CLIENT_BUILDERS: dict[
    str,
    ModelClientBuilder,
] = {
    "development": _build_development_client,
    "openai_compatible": (
        _build_openai_compatible_client
    ),
}


def build_model_client(
    profile: ModelProfile,
) -> ModelClient:
    """Build a model client from a validated model profile."""

    if not profile.enabled:
        raise DisabledModelProfileError(
            profile_key=profile.profile_key,
        )

    builder = _CLIENT_BUILDERS.get(
        profile.adapter_type
    )

    if builder is None:
        raise UnsupportedModelAdapterError(
            adapter_type=profile.adapter_type,
        )

    return builder(
        profile
    )