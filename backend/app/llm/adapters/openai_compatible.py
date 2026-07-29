import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.capabilities import ModelCapabilities
from app.llm.contracts import (
    ModelFinishReason,
    ModelRequest,
    ModelResponse,
    ModelStreamCompleted,
    ModelStreamEvent,
    ModelStreamTextDelta,
    ModelUsage,
)
from app.llm.model_profiles import ModelProfile
from app.llm.runtime import ModelClientError


class OpenAICompatibleModelClientError(ModelClientError):
    """Base error raised by the OpenAI-compatible adapter."""


class OpenAICompatibleConfigurationError(
    OpenAICompatibleModelClientError
):
    """Raised when an adapter profile is not usable."""


class OpenAICompatibleConnectionError(
    OpenAICompatibleModelClientError
):
    """Raised when the configured model server cannot be reached."""


class OpenAICompatibleResponseError(
    OpenAICompatibleModelClientError
):
    """Raised when the model server returns an invalid response."""


class OpenAICompatibleModelClient:
    """
    Model client for servers implementing the OpenAI-compatible
    chat-completions API.

    This first implementation uses NORA's structured-JSON tool flow.
    Native provider tool calls will be added separately.
    """

    def __init__(
        self,
        profile: ModelProfile,
    ) -> None:
        if profile.adapter_type != "openai_compatible":
            raise OpenAICompatibleConfigurationError(
                "The profile must use the openai_compatible adapter."
            )

        if not profile.base_url:
            raise OpenAICompatibleConfigurationError(
                "The profile must define a base_url."
            )

        if profile.tool_mode != "structured_json":
            raise OpenAICompatibleConfigurationError(
                "The OpenAI-compatible adapter currently supports "
                "structured_json tool mode only."
            )

        self._profile = profile
        self._base_url = profile.base_url.rstrip("/")

    @property
    def capabilities(self) -> ModelCapabilities:
        """Return the capabilities declared by the profile."""

        return self._profile.capabilities

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        """Send a normalized request to the configured model server."""

        if request.stream:
            raise OpenAICompatibleConfigurationError(
                "Streaming requests must use the stream method."
            )

        endpoint = f"{self._base_url}/chat/completions"

        payload = self._build_payload(
            request=request,
        )

        headers = self._build_headers()

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    self._profile.request_timeout_seconds
                )
            ) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                )

                response.raise_for_status()

        except httpx.TimeoutException as error:
            raise OpenAICompatibleConnectionError(
                "The model request timed out."
            ) from error

        except httpx.HTTPStatusError as error:
            response_preview = error.response.text[:500]

            raise OpenAICompatibleResponseError(
                "The model server returned HTTP "
                f"{error.response.status_code}: "
                f"{response_preview}"
            ) from error

        except httpx.RequestError as error:
            raise OpenAICompatibleConnectionError(
                "NORA could not connect to the configured "
                "model server."
            ) from error

        try:
            response_data = response.json()
        except ValueError as error:
            raise OpenAICompatibleResponseError(
                "The model server did not return valid JSON."
            ) from error

        return self._parse_response(
            response_data=response_data,
        )

    async def stream(
        self,
        request: ModelRequest,
    ) -> AsyncIterator[ModelStreamEvent]:
        """
        Stream provider output as normalized model events.

        OpenAI-compatible SSE frames are consumed inside this adapter.
        Provider-native frames are never exposed to the conversation or
        API layers.
        """

        if not request.stream:
            raise OpenAICompatibleConfigurationError(
                "Streaming requests must set request.stream to True."
            )

        endpoint = f"{self._base_url}/chat/completions"

        payload = self._build_payload(
            request=request,
        )

        headers = self._build_headers()
        headers["Accept"] = "text/event-stream"

        text_fragments: list[str] = []

        finish_reason: ModelFinishReason = "unknown"

        usage: ModelUsage | None = None

        returned_model_name = self._profile.model_name

        last_response_data: dict[str, Any] | None = None

        received_stream_data = False

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    self._profile.request_timeout_seconds
                )
            ) as client:
                async with client.stream(
                    "POST",
                    endpoint,
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()

                        response_preview = response.text[:500]

                        raise OpenAICompatibleResponseError(
                            "The model server returned HTTP "
                            f"{response.status_code}: "
                            f"{response_preview}"
                        )

                    async for line in response.aiter_lines():
                        stripped_line = line.strip()

                        if not stripped_line:
                            continue

                        if stripped_line.startswith(":"):
                            continue

                        if stripped_line.startswith(
                            (
                                "event:",
                                "id:",
                                "retry:",
                            )
                        ):
                            continue

                        if not stripped_line.startswith("data:"):
                            raise OpenAICompatibleResponseError(
                                "The model stream contained an invalid "
                                "SSE line."
                            )

                        raw_data = stripped_line[
                            len("data:"):
                        ].strip()

                        if raw_data == "[DONE]":
                            break

                        if not raw_data:
                            continue

                        try:
                            response_data = json.loads(
                                raw_data
                            )
                        except json.JSONDecodeError as error:
                            raise OpenAICompatibleResponseError(
                                "The model stream contained invalid "
                                "JSON."
                            ) from error

                        if not isinstance(response_data, dict):
                            raise OpenAICompatibleResponseError(
                                "Each model stream frame must contain "
                                "a JSON object."
                            )

                        received_stream_data = True
                        last_response_data = response_data

                        raw_model_name = response_data.get(
                            "model"
                        )

                        if isinstance(raw_model_name, str):
                            returned_model_name = raw_model_name

                        parsed_usage = self._parse_usage(
                            raw_usage=response_data.get("usage"),
                        )

                        if parsed_usage is not None:
                            usage = parsed_usage

                        (
                            content,
                            chunk_finish_reason,
                        ) = self._parse_stream_chunk(
                            response_data=response_data,
                        )

                        if chunk_finish_reason is not None:
                            finish_reason = chunk_finish_reason

                        if content is None:
                            continue

                        text_fragments.append(
                            content
                        )

                        yield ModelStreamTextDelta(
                            content=content,
                        )

        except httpx.TimeoutException as error:
            raise OpenAICompatibleConnectionError(
                "The model streaming request timed out."
            ) from error

        except httpx.RequestError as error:
            raise OpenAICompatibleConnectionError(
                "NORA could not connect to the configured "
                "model server."
            ) from error

        if not received_stream_data:
            raise OpenAICompatibleResponseError(
                "The model server did not return any stream data."
            )

        complete_text = "".join(
            text_fragments
        )

        if not complete_text.strip():
            raise OpenAICompatibleResponseError(
                "The model stream did not contain usable text."
            )

        completed_response = ModelResponse(
            text=complete_text,
            finish_reason=finish_reason,
            usage=usage,
            provider_name=self._profile.provider_name,
            model_name=returned_model_name,
            raw_response=last_response_data,
        )

        yield ModelStreamCompleted(
            response=completed_response,
        )

    def _build_payload(
        self,
        *,
        request: ModelRequest,
    ) -> dict[str, Any]:
        messages = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in request.messages
        ]

        maximum_output_tokens = min(
            request.max_output_tokens,
            self._profile.maximum_output_tokens,
        )

        capabilities = self._profile.capabilities

        payload: dict[str, Any] = {
            "model": self._profile.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "stream": request.stream,
        }

        output_token_parameter = (
            capabilities.output_token_parameter
        )

        if output_token_parameter != "none":
            payload[
                output_token_parameter
            ] = maximum_output_tokens

        if (
            self._profile.reasoning_effort is not None
            and capabilities.supports_reasoning_effort
        ):
            payload["reasoning_effort"] = (
                self._profile.reasoning_effort
            )

        if (
            request.response_format == "json_object"
            and capabilities
            .accepts_response_format_json_object
        ):
            payload["response_format"] = {
                "type": "json_object",
            }

        return payload

    def _build_headers(
        self,
    ) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        credential_env_var = (
            self._profile.credential_env_var
        )

        if credential_env_var is None:
            return headers

        credential = os.getenv(
            credential_env_var
        )

        if not credential:
            raise OpenAICompatibleConfigurationError(
                "The model credential environment variable "
                f"'{credential_env_var}' is not configured."
            )

        headers["Authorization"] = (
            f"Bearer {credential}"
        )

        return headers

    def _parse_response(
        self,
        *,
        response_data: Any,
    ) -> ModelResponse:
        if not isinstance(response_data, dict):
            raise OpenAICompatibleResponseError(
                "The model response must be a JSON object."
            )

        choices = response_data.get("choices")

        if not isinstance(choices, list) or not choices:
            raise OpenAICompatibleResponseError(
                "The model response did not contain any choices."
            )

        first_choice = choices[0]

        if not isinstance(first_choice, dict):
            raise OpenAICompatibleResponseError(
                "The first model choice was invalid."
            )

        finish_reason = self._normalize_finish_reason(
            first_choice.get("finish_reason")
        )

        message = first_choice.get("message")

        if not isinstance(message, dict):
            raise OpenAICompatibleResponseError(
                "The first model choice did not contain a message."
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise OpenAICompatibleResponseError(
                "The model response did not contain usable text."
            )

        returned_model_name = response_data.get(
            "model"
        )

        if not isinstance(returned_model_name, str):
            returned_model_name = (
                self._profile.model_name
            )

        usage = self._parse_usage(
            raw_usage=response_data.get("usage"),
        )

        return ModelResponse(
            text=content,
            finish_reason=finish_reason,
            usage=usage,
            provider_name=self._profile.provider_name,
            model_name=returned_model_name,
            raw_response=response_data,
        )

    def _parse_stream_chunk(
        self,
        *,
        response_data: dict[str, Any],
    ) -> tuple[
        str | None,
        ModelFinishReason | None,
    ]:
        """Extract text and finish information from one stream chunk."""

        choices = response_data.get("choices")

        if not isinstance(choices, list):
            raise OpenAICompatibleResponseError(
                "The model stream frame did not contain a valid "
                "choices list."
            )

        if not choices:
            return (
                None,
                None,
            )

        first_choice = choices[0]

        if not isinstance(first_choice, dict):
            raise OpenAICompatibleResponseError(
                "The first streamed model choice was invalid."
            )

        raw_finish_reason = first_choice.get(
            "finish_reason"
        )

        finish_reason: ModelFinishReason | None = None

        if raw_finish_reason is not None:
            finish_reason = self._normalize_finish_reason(
                raw_finish_reason
            )

        delta = first_choice.get("delta")

        if delta is None:
            return (
                None,
                finish_reason,
            )

        if not isinstance(delta, dict):
            raise OpenAICompatibleResponseError(
                "The streamed model choice contained an invalid "
                "delta."
            )

        content = delta.get("content")

        if content is None or content == "":
            return (
                None,
                finish_reason,
            )

        if not isinstance(content, str):
            raise OpenAICompatibleResponseError(
                "The streamed model content delta must be text."
            )

        return (
            content,
            finish_reason,
        )

    def _normalize_finish_reason(
        self,
        value: Any,
    ) -> ModelFinishReason:
        """Normalize provider finish reasons into NORA's contract."""

        if value == "stop":
            return "stop"

        if value == "length":
            return "length"

        if value == "content_filter":
            return "content_filter"

        if value == "error":
            return "error"

        if value in {
            "tool_call",
            "tool_calls",
            "function_call",
        }:
            return "tool_call"

        return "unknown"

    def _parse_usage(
        self,
        *,
        raw_usage: Any,
    ) -> ModelUsage | None:
        """Normalize OpenAI-compatible token-usage fields."""

        if not isinstance(raw_usage, dict):
            return None

        input_tokens = self._read_nonnegative_integer(
            raw_usage.get("prompt_tokens")
        )

        output_tokens = self._read_nonnegative_integer(
            raw_usage.get("completion_tokens")
        )

        total_tokens = self._read_nonnegative_integer(
            raw_usage.get("total_tokens")
        )

        if (
            total_tokens is None
            and input_tokens is not None
            and output_tokens is not None
        ):
            total_tokens = (
                input_tokens
                + output_tokens
            )

        if (
            input_tokens is None
            and output_tokens is None
            and total_tokens is None
        ):
            return None

        return ModelUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    def _read_nonnegative_integer(
        self,
        value: Any,
    ) -> int | None:
        """Return a valid nonnegative integer from provider data."""

        if isinstance(value, bool):
            return None

        if not isinstance(value, int):
            return None

        if value < 0:
            return None

        return value