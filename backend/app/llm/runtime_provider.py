from dataclasses import dataclass

from app.llm.model_profiles import ModelProfile
from app.llm.runtime import ModelClient


class ModelClientNotConfiguredError(Exception):
    """Raised when no model runtime has been configured."""


@dataclass(
    frozen=True,
    slots=True,
)
class ConfiguredModelRuntime:
    """
    Bind the active model client to the exact profile used to build it.

    Keeping these values together prevents request handling and
    persistence from independently resolving different profiles.
    """

    client: ModelClient
    profile: ModelProfile


_model_runtime: ConfiguredModelRuntime | None = None


def configure_model_runtime(
    *,
    client: ModelClient,
    profile: ModelProfile,
) -> ConfiguredModelRuntime:
    """Configure the process-wide model client and profile."""

    runtime = ConfiguredModelRuntime(
        client=client,
        profile=profile,
    )

    global _model_runtime
    _model_runtime = runtime

    return runtime


def get_model_runtime() -> ConfiguredModelRuntime:
    """Return the configured client and its exact model profile."""

    if _model_runtime is None:
        raise ModelClientNotConfiguredError(
            "A model runtime has not been configured."
        )

    return _model_runtime


def get_model_client() -> ModelClient:
    """
    Return the configured model client.

    This compatibility helper may be removed after all callers use the
    configured runtime directly.
    """

    return get_model_runtime().client