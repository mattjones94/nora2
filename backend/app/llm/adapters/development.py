import json
from datetime import datetime
from typing import Any

from app.llm.capabilities import ModelCapabilities
from app.llm.contracts import (
    ModelRequest,
    ModelResponse,
)
from app.llm.runtime import ModelClientError


class DevelopmentModelClient:
    """
    Deterministic model client used to test NORA without a real LLM.

    It implements the same provider-neutral interface that future
    OpenAI-compatible, Anthropic, Ollama, and LiteRT-LM adapters will use.
    """

    def __init__(
        self,
        model_name: str = "deterministic-test-client",
    ) -> None:
        self._model_name = model_name

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_native_tools=False,
            supports_structured_output=True,
            supports_streaming=False,
            supports_system_messages=True,
            supports_multiple_tool_calls=False,
            supports_vision=False,
            maximum_context_tokens=8192,
            maximum_output_tokens=512,
        )

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        prompt = self._extract_prompt(
            request=request,
        )

        if "Verified tool result:" in prompt:
            tool_result = self._extract_json_after_marker(
                prompt=prompt,
                marker="Verified tool result:",
            )

            if not isinstance(tool_result, dict):
                raise ModelClientError(
                    "The development client received an invalid tool result."
                )

            return ModelResponse(
                text=json.dumps(
                    {
                        "action": "respond",
                        "message": self._build_event_response(
                            tool_result=tool_result,
                        ),
                    }
                ),
                finish_reason="stop",
                provider_name="development",
                model_name=self._model_name,
            )

        if "User message:" in prompt:
            user_message = self._extract_json_after_marker(
                prompt=prompt,
                marker="User message:",
            )

            if not isinstance(user_message, str):
                raise ModelClientError(
                    "The development client received an invalid user message."
                )

            normalized_message = user_message.lower()

            if (
                "student life" in normalized_message
                and "event" in normalized_message
            ):
                return ModelResponse(
                    text=json.dumps(
                        {
                            "action": "tool_call",
                            "tool_name": "get_upcoming_events",
                            "arguments": {
                                "department_slug": "student-life",
                                "limit": 10,
                            },
                        }
                    ),
                    finish_reason="stop",
                    provider_name="development",
                    model_name=self._model_name,
                )

            return ModelResponse(
                text=json.dumps(
                    {
                        "action": "respond",
                        "message": (
                            "I can currently help test questions about "
                            "upcoming Student Life events."
                        ),
                    }
                ),
                finish_reason="stop",
                provider_name="development",
                model_name=self._model_name,
            )

        raise ModelClientError(
            "The development client did not recognize the request."
        )

    def _extract_prompt(
        self,
        *,
        request: ModelRequest,
    ) -> str:
        for message in reversed(request.messages):
            if message.content and message.content.strip():
                return message.content

        raise ModelClientError(
            "The model request did not contain a usable message."
        )

    def _extract_json_after_marker(
        self,
        *,
        prompt: str,
        marker: str,
    ) -> Any:
        marker_position = prompt.find(marker)

        if marker_position == -1:
            raise ModelClientError(
                f'The prompt did not contain the marker "{marker}".'
            )

        json_text = prompt[
            marker_position + len(marker):
        ].lstrip()

        try:
            value, _ = json.JSONDecoder().raw_decode(
                json_text
            )
        except json.JSONDecodeError as error:
            raise ModelClientError(
                f"Unable to parse prompt data: {error.msg}"
            ) from error

        return value

    def _build_event_response(
        self,
        *,
        tool_result: dict[str, Any],
    ) -> str:
        department_name = str(
            tool_result.get(
                "department_name",
                "The department",
            )
        )

        events = tool_result.get(
            "events",
            [],
        )

        if not isinstance(events, list) or not events:
            return (
                f"{department_name} does not currently have any "
                "active upcoming events listed."
            )

        event_descriptions: list[str] = []

        for event in events:
            if not isinstance(event, dict):
                continue

            title = str(
                event.get(
                    "title",
                    "Unnamed event",
                )
            )

            description = title
            starts_at = event.get("starts_at")

            if isinstance(starts_at, str):
                description += (
                    f" on {self._format_datetime(starts_at)}"
                )

            location = event.get("location")

            if isinstance(location, str) and location:
                description += f" at {location}"

            event_descriptions.append(
                description
            )

        if not event_descriptions:
            return (
                f"{department_name} does not currently have any "
                "active upcoming events listed."
            )

        return (
            f"{department_name} has {len(event_descriptions)} "
            f"upcoming events: {'; '.join(event_descriptions)}."
        )

    def _format_datetime(
        self,
        value: str,
    ) -> str:
        try:
            parsed_value = datetime.fromisoformat(
                value
            )
        except ValueError:
            return value

        date_text = (
            f"{parsed_value.strftime('%B')} "
            f"{parsed_value.day}, "
            f"{parsed_value.year}"
        )

        time_text = parsed_value.strftime(
            "%I:%M %p"
        ).lstrip("0")

        return f"{date_text} at {time_text}"