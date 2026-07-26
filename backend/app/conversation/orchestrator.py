from collections.abc import Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.response_contracts import (
    ConversationTurnResult,
)
from app.llm.contracts import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelToolDefinition,
)
from app.llm.prompt_builder import (
    build_action_prompt,
    build_tool_result_prompt,
)
from app.llm.runtime import ModelClient
from app.llm.tool_calling import (
    RespondAction,
    ToolCallAction,
    execute_tool_call_action,
    parse_model_action,
)
from app.llm.tool_registry import get_tool_catalog
from app.tools.context import ToolContext
from app.tools.errors import ToolExecutionError


class ConversationOrchestrationError(Exception):
    """Base error raised while coordinating a conversation turn."""


class UnexpectedFollowUpActionError(
    ConversationOrchestrationError
):
    """Raised when the model requests another tool after receiving results."""

    def __init__(self) -> None:
        super().__init__(
            "The model must provide a response after receiving a tool result."
        )


class ConversationOrchestrator:
    """Coordinate model decisions, tool execution, and final responses."""

    def __init__(
        self,
        client: ModelClient,
    ) -> None:
        self._client = client

    async def handle_message(
        self,
        *,
        user_message: str,
        session: AsyncSession,
        context: ToolContext,
        conversation_history: Sequence[
            Mapping[str, str]
        ] = (),
    ) -> ConversationTurnResult:
        """Process one user message within trusted organization scope."""

        tool_catalog = get_tool_catalog()

        tool_definitions = [
            ModelToolDefinition.model_validate(
                tool_entry
            )
            for tool_entry in tool_catalog
        ]

        action_prompt = build_action_prompt(
            user_message=user_message,
            organization_slug=context.organization_slug,
            tool_catalog=tool_catalog,
            conversation_history=conversation_history,
        )

        action_response = await self._client.generate(
            request=ModelRequest(
                messages=[
                    ModelMessage(
                        role="user",
                        content=action_prompt,
                    ),
                ],
                tools=tool_definitions,
                response_format="json_object",
                temperature=0.0,
                max_output_tokens=self._get_output_limit(),
                stream=False,
                metadata={
                    "request_type": "action_selection",
                    "organization_slug": (
                        context.organization_slug
                    ),
                },
            )
        )

        model_action = self._response_to_action(
            response=action_response,
        )

        if isinstance(model_action, RespondAction):
            return self._build_turn_result(
                action=model_action,
                responses=(
                    action_response,
                ),
            )

        if not isinstance(model_action, ToolCallAction):
            raise ConversationOrchestrationError(
                "The model returned an unsupported action."
            )

        try:
            tool_result = await execute_tool_call_action(
                action=model_action,
                session=session,
                context=context,
            )

        except ToolExecutionError:
            clarification_action = RespondAction(
                action="respond",
                message=(
                    "I could not determine the exact department or "
                    "information you meant. Please name the department "
                    "you would like me to check."
                ),
            )

            return self._build_turn_result(
                action=clarification_action,
                responses=(
                    action_response,
                ),
                tool_call_count=1,
                successful_tool_call_count=0,
            )

        result_prompt = build_tool_result_prompt(
            user_message=user_message,
            tool_name=model_action.tool_name,
            tool_result=tool_result.model_dump(
                mode="json",
            ),
        )

        final_response = await self._client.generate(
            request=ModelRequest(
                messages=[
                    ModelMessage(
                        role="user",
                        content=result_prompt,
                    ),
                ],
                response_format="json_object",
                temperature=0.0,
                max_output_tokens=self._get_output_limit(),
                stream=False,
                metadata={
                    "request_type": "tool_result_response",
                    "organization_slug": (
                        context.organization_slug
                    ),
                    "tool_name": model_action.tool_name,
                },
            )
        )

        if final_response.tool_calls:
            raise UnexpectedFollowUpActionError()

        final_action = self._response_to_action(
            response=final_response,
        )

        if not isinstance(final_action, RespondAction):
            raise UnexpectedFollowUpActionError()

        return self._build_turn_result(
            action=final_action,
            responses=(
                action_response,
                final_response,
            ),
            tool_call_count=1,
            successful_tool_call_count=1,
        )

    def _response_to_action(
        self,
        *,
        response: ModelResponse,
    ) -> ToolCallAction | RespondAction:
        """
        Convert either normalized native tool calls or structured JSON
        text into NORA's validated action contract.
        """

        if response.tool_calls:
            if len(response.tool_calls) != 1:
                raise ConversationOrchestrationError(
                    "Only one model tool call is currently supported per turn."
                )

            tool_call = response.tool_calls[0]

            return ToolCallAction(
                action="tool_call",
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
            )

        if response.text is None:
            raise ConversationOrchestrationError(
                "The model response did not contain text or a tool call."
            )

        return parse_model_action(
            raw_output=response.text,
        )

    def _build_turn_result(
        self,
        *,
        action: RespondAction,
        responses: Sequence[ModelResponse],
        tool_call_count: int = 0,
        successful_tool_call_count: int = 0,
    ) -> ConversationTurnResult:
        """Build the final result returned for one conversation turn."""

        input_tokens = self._sum_usage_field(
            responses=responses,
            field_name="input_tokens",
        )

        output_tokens = self._sum_usage_field(
            responses=responses,
            field_name="output_tokens",
        )

        total_tokens = self._sum_usage_field(
            responses=responses,
            field_name="total_tokens",
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

        final_response = responses[-1]

        return ConversationTurnResult(
            message=action.message,
            provider_name=final_response.provider_name,
            model_name=final_response.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tool_call_count=tool_call_count,
            successful_tool_call_count=(
                successful_tool_call_count
            ),
        )

    def _sum_usage_field(
        self,
        *,
        responses: Sequence[ModelResponse],
        field_name: str,
    ) -> int | None:
        """Sum one normalized usage field across model calls."""

        values: list[int] = []

        for response in responses:
            if response.usage is None:
                continue

            value = getattr(
                response.usage,
                field_name,
                None,
            )

            if value is not None:
                values.append(
                    value
                )

        if not values:
            return None

        return sum(
            values
        )

    def _get_output_limit(self) -> int:
        configured_limit = (
            self._client.capabilities.maximum_output_tokens
        )

        if configured_limit is None:
            return 512

        return min(
            512,
            configured_limit,
        )