import os
from collections.abc import Callable

from app.llm.model_profiles import (
    ModelProfile,
    create_development_model_profile,
)

from app.llm.model_profiles import (
    ModelProfile,
    create_development_model_profile,
    create_ollama_qwen3_1_7b_profile,
)


class ModelProfileRegistryError(Exception):
    """Base error raised while resolving a model profile."""


class ModelProfileNotFoundError(ModelProfileRegistryError):
    """Raised when the configured profile key is unavailable."""

    def __init__(self, profile_key: str) -> None:
        super().__init__(
            f"Model profile '{profile_key}' was not found."
        )


ModelProfileBuilder = Callable[[], ModelProfile]


_PROFILE_BUILDERS: dict[str, ModelProfileBuilder] = {
    "development-default": (
        create_development_model_profile
    ),
    "ollama-qwen3-1.7b": (
        create_ollama_qwen3_1_7b_profile
    )
}


def get_model_profile(
    profile_key: str,
) -> ModelProfile:
    """Return a configured model profile by its stable key."""

    normalized_key = profile_key.strip().lower()

    builder = _PROFILE_BUILDERS.get(
        normalized_key
    )

    if builder is None:
        raise ModelProfileNotFoundError(
            profile_key=normalized_key,
        )

    return builder()


def get_default_model_profile() -> ModelProfile:
    """Return the model profile selected for this deployment."""

    profile_key = os.getenv(
        "NORA_MODEL_PROFILE",
        "development-default",
    )

    return get_model_profile(
        profile_key=profile_key,
    )