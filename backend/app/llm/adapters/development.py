import json
from collections import deque
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from app.llm.capabilities import ModelCapabilities
from app.llm.contracts import (
    ModelRequest,
    ModelRequestPurpose,
    ModelResponse,
    ModelStreamCompleted,
    ModelStreamEvent,
    ModelStreamTextDelta,
)
from app.llm.model_profiles import ModelProfile
from app.llm.runtime import ModelClientError

_DEVELOPMENT_STREAM_CHUNK_SIZE = 24


class DevelopmentModelClientError(ModelClientError):
    """Base error raised by the deterministic development adapter."""


class DevelopmentModelConfigurationError(
    DevelopmentModelClientError
):
    """Raised when the selected profile cannot use this adapter."""


class DevelopmentScriptPurposeMismatchError(
    DevelopmentModelClientError
):
    """Raised when a scripted step does not match the request purpose."""

    def __init__(
        self,
        *,
        expected_purpose: ModelRequestPurpose,
        actual_purpose: ModelRequestPurpose,
    ) -> None:
        self.expected_purpose = expected_purpose
        self.actual_purpose = actual_purpose

        super().__init__(
            "The next scripted development response expected request "
            f"purpose '{expected_purpose}', but received "
            f"'{actual_purpose}'."
        )


@dataclass(
    frozen=True,
    slots=True,
)
class DevelopmentScriptStep:
    """One expected request and deterministic model response."""

    purpose: ModelRequestPurpose
    response: ModelResponse


class DevelopmentModelClient:
    """
    Generic deterministic client for testing NORA without a real model.

    Tests may supply ordered script steps. When no script is supplied,
    the client returns a safe generic response rather than containing
    feature-specific or organization-specific behavior.
    """

    def __init__(
        self,
        *,
        profile: ModelProfile,
        script: Sequence[DevelopmentScriptStep] = (),
    ) -> None:
        if profile.adapter_type != "development":
            raise DevelopmentModelConfigurationError(
                "The profile must use the development adapter."
            )

        self._profile = profile

        self._script = deque(
            script
        )

        self._requests: list[ModelRequest] = []

    @property
    def capabilities(self) -> ModelCapabilities:
        """Return capabilities declared by the selected profile."""

        return self._profile.capabilities

    @property
    def requests(self) -> tuple[ModelRequest, ...]:
        """Return requests received by this client in call order."""

        return tuple(
            self._requests
        )

    @property
    def remaining_script_steps(self) -> int:
        """Return the number of scripted responses not yet consumed."""

        return len(
            self._script
        )

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        """Return the next scripted or safe default response."""

        self._requests.append(
            request
        )

        if self._script:
            script_step = self._script.popleft()

            if script_step.purpose != request.purpose:
                raise DevelopmentScriptPurposeMismatchError(
                    expected_purpose=script_step.purpose,
                    actual_purpose=request.purpose,
                )

            return self._normalize_response(
                response=script_step.response,
            )

        return self._build_default_response(
            request=request,
        )
    

    async def stream(
        self,
        request: ModelRequest,
    ) -> AsyncIterator[ModelStreamEvent]:
        """
        Yield deterministic text fragments and one completed response.

        The development adapter reuses generate() so scripted response
        selection, request recording, purpose validation, default
        behavior, and profile normalization remain identical between
        delivery modes.
        """

        response = await self.generate(
            request
        )

        if (
            response.text is None
            or not response.text.strip()
        ):
            raise DevelopmentModelClientError(
                "The deterministic development stream requires a "
                "response containing public text."
            )

        for start_index in range(
            0,
            len(response.text),
            _DEVELOPMENT_STREAM_CHUNK_SIZE,
        ):
            yield ModelStreamTextDelta(
                content=response.text[
                    start_index:
                    start_index
                    + _DEVELOPMENT_STREAM_CHUNK_SIZE
                ],
            )

        yield ModelStreamCompleted(
            response=response,
        )

    def _build_default_response(
        self,
        *,
        request: ModelRequest,
    ) -> ModelResponse:
        """Return a safe response when no test script was configured."""

        message = (
            "The deterministic development model is active, but no "
            "scripted response was configured for this request."
        )

        if request.purpose in {
            "action_selection",
            "action_repair",
        }:
            response_text = json.dumps(
                {
                    "action": "respond",
                    "message": message,
                }
            )
        elif request.purpose == "tool_result_synthesis":
            response_text = message
        else:
            raise DevelopmentModelClientError(
                "The development client does not support request "
                f"purpose '{request.purpose}'."
            )

        return ModelResponse(
            text=response_text,
            finish_reason="stop",
            provider_name=self._profile.provider_name,
            model_name=self._profile.model_name,
        )

    def _normalize_response(
        self,
        *,
        response: ModelResponse,
    ) -> ModelResponse:
        """Apply profile identity when a script omits provider metadata."""

        updates: dict[str, str] = {}

        if response.provider_name is None:
            updates["provider_name"] = (
                self._profile.provider_name
            )

        if response.model_name is None:
            updates["model_name"] = (
                self._profile.model_name
            )

        if not updates:
            return response

        return response.model_copy(
            update=updates,
        )