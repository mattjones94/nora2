from app.llm.runtime import ModelClient


class ModelClientNotConfiguredError(Exception):
    """Raised when no model client has been configured."""


_model_client: ModelClient | None = None


def configure_model_client(
    client: ModelClient,
) -> None:
    """Configure the process-wide model client."""

    global _model_client
    _model_client = client


def get_model_client() -> ModelClient:
    """Return the configured model client."""

    if _model_client is None:
        raise ModelClientNotConfiguredError(
            "A model client has not been configured."
        )

    return _model_client