from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.llm.capabilities import ModelCapabilities
from app.llm.contracts import (
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)


class ModelClientError(Exception):
    """Base error raised by a configured model client."""


@runtime_checkable
class ModelClient(Protocol):
    """Provider-neutral interface implemented by model adapters."""

    @property
    def capabilities(self) -> ModelCapabilities:
        """Return the capabilities of the configured model."""
        ...

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        """Generate a normalized model response."""

    def stream(
        self,
        request: ModelRequest,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Generate provider-neutral streaming response events."""