##backend/app/conversation/orchestrator.py

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter_ns

from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.response_contracts import (
    ConversationStreamCompleted,
    ConversationStreamEvent,
    ConversationStreamTextDelta,
    ConversationToolContextRecord,
    ConversationToolExecutionRecord,
    ConversationToolResultRecord,
    ConversationTurnResult,
    ToolExecutionAttemptPhase,
)

from app.conversation.tool_batch import (
    ToolBatchExecutionResult,
    execute_tool_batch,
)
from app.llm.contracts import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamCompleted,
    ModelStreamTextDelta,
    ModelToolDefinition,
)
from app.llm.errors import (
    InvalidToolArgumentsError,
    ModelProtocolError,
    UnknownToolError,
)
from app.llm.prompt_builder import (
    build_action_messages,
    build_action_repair_messages,
    build_tool_results_prompt,
)
from app.llm.runtime import ModelClient
from app.llm.tool_calling import (
    MAX_TOOL_CALLS_PER_ACTION,
    RespondAction,
    ToolCallAction,
    ToolCallsAction,
    parse_model_action,
)
from app.llm.tool_registry import (
    get_registered_tool,
    get_tool_catalog,
)
from app.tools.context import ToolContext


_PROTOCOL_FALLBACK_MESSAGE = (
    "I'm sorry, but I could not process that request reliably. "
    "Please rephrase your question and try again."
)

_PARTIAL_TOOL_FAILURE_MESSAGE = (
    "I could not retrieve one or more of the other "
    "requested items from the published organization data."
)


class ConversationOrchestrationError(Exception):
    """Base error raised while coordinating a conversation turn."""


class UnexpectedFollowUpActionError(
    ConversationOrchestrationError
):
    """Raised when the model requests another tool after receiving results."""

    def __init__(self) -> None:
        super().__init__(
            "The model must provide a response after receiving "
            "a tool result."
        )


@dataclass(
    frozen=True,
    slots=True,
)
class _ActionAttemptResult:
    """Internal result from interpreting one model action."""

    action: (
        RespondAction
        | ToolCallAction
        | ToolCallsAction
    )

    batch_result: ToolBatchExecutionResult | None = None

    @property
    def tool_call_count(self) -> int:
        """Return the number of executed tool calls."""

        if self.batch_result is None:
            return 0

        return self.batch_result.tool_call_count

    @property
    def successful_tool_call_count(self) -> int:
        """Return the number of successful tool calls."""

        if self.batch_result is None:
            return 0

        return (
            self.batch_result
            .successful_tool_call_count
        )


@dataclass(
    frozen=True,
    slots=True,
)
class _PreparedSynthesisTurn:
    """Internal state required to complete one tool-backed turn."""

    request: ModelRequest

    model_responses: tuple[
        ModelResponse,
        ...
    ]

    tool_call_count: int
    successful_tool_call_count: int

    tool_executions: tuple[
        ConversationToolExecutionRecord,
        ...
    ]

    tool_results: tuple[
        ConversationToolResultRecord,
        ...
    ]

    has_tool_failures: bool


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
        tool_context_history: Sequence[
            ConversationToolContextRecord
        ] = (),
    ) -> ConversationTurnResult:
        """Process one user message within trusted organization scope."""

        prepared_turn = await self._prepare_turn(
            user_message=user_message,
            session=session,
            context=context,
            conversation_history=conversation_history,
            tool_context_history=tool_context_history,
        )

        if isinstance(
            prepared_turn,
            ConversationTurnResult,
        ):
            return prepared_turn

        return await self._complete_prepared_turn(
            prepared_turn=prepared_turn,
        )

    async def stream_message(
        self,
        *,
        user_message: str,
        session: AsyncSession,
        context: ToolContext,
        conversation_history: Sequence[
            Mapping[str, str]
        ] = (),
        tool_context_history: Sequence[
            ConversationToolContextRecord
        ] = (),
    ) -> AsyncIterator[ConversationStreamEvent]:
        """
        Process one turn and stream only public assistant text.

        Action selection, repair, validation, and tool execution reuse
        the same preparation path as the non-streaming method.
        """

        prepared_turn = await self._prepare_turn(
            user_message=user_message,
            session=session,
            context=context,
            conversation_history=conversation_history,
            tool_context_history=tool_context_history,
        )

        if isinstance(
            prepared_turn,
            ConversationTurnResult,
        ):
            yield ConversationStreamTextDelta(
                content=prepared_turn.message,
            )

            yield ConversationStreamCompleted(
                result=prepared_turn,
            )

            return

        async for event in self._stream_prepared_turn(
            prepared_turn=prepared_turn,
        ):
            yield event

    async def _stream_prepared_turn(
        self,
        *,
        prepared_turn: _PreparedSynthesisTurn,
    ) -> AsyncIterator[ConversationStreamEvent]:
        """Stream and finalize one prepared tool-backed turn."""

        stream_request = prepared_turn.request.model_copy(
            update={
                "stream": True,
            },
        )

        text_fragments: list[str] = []

        completed_response: ModelResponse | None = None

        async for event in self._client.stream(
            request=stream_request,
        ):
            if isinstance(
                event,
                ModelStreamTextDelta,
            ):
                if completed_response is not None:
                    raise ConversationOrchestrationError(
                        "The model stream produced text after its "
                        "completion event."
                    )

                text_fragments.append(
                    event.content
                )

                yield ConversationStreamTextDelta(
                    content=event.content,
                )

                continue

            if isinstance(
                event,
                ModelStreamCompleted,
            ):
                if completed_response is not None:
                    raise ConversationOrchestrationError(
                        "The model stream produced more than one "
                        "completion event."
                    )

                completed_response = event.response

                continue

            raise ConversationOrchestrationError(
                "The model stream produced an unsupported event."
            )

        if completed_response is None:
            raise ConversationOrchestrationError(
                "The model stream ended without a completion event."
            )

        if not text_fragments:
            raise ConversationOrchestrationError(
                "The model stream ended without public text deltas."
            )

        joined_text = "".join(
            text_fragments
        )

        if completed_response.text != joined_text:
            raise ConversationOrchestrationError(
                "The completed model response did not match the "
                "ordered stream deltas."
            )

        completed_result = self._finalize_prepared_turn(
            prepared_turn=prepared_turn,
            final_response=completed_response,
        )

        if prepared_turn.has_tool_failures:
            yield ConversationStreamTextDelta(
                content=(
                    f"\n\n{_PARTIAL_TOOL_FAILURE_MESSAGE}"
                ),
            )

        yield ConversationStreamCompleted(
            result=completed_result,
        )

    async def _prepare_turn(
        self,
        *,
        user_message: str,
        session: AsyncSession,
        context: ToolContext,
        conversation_history: Sequence[
            Mapping[str, str]
        ] = (),
        tool_context_history: Sequence[
            ConversationToolContextRecord
        ] = (),
    ) -> (
        ConversationTurnResult
        | _PreparedSynthesisTurn
    ):
        """
        Run shared action selection, repair, and tool execution.

        Direct responses and safe fallbacks return completed turn
        results. Successful tool-backed turns return the normalized
        synthesis work required by either completion delivery mode.
        """

        tool_context_mappings = tuple(
            {
                "sequence_number": (
                    tool_context.sequence_number
                ),
                "tool_name": tool_context.tool_name,
                "validated_arguments_json": dict(
                    tool_context
                    .validated_arguments_json
                ),
                "result_json": dict(
                    tool_context.result_json
                ),
            }
            for tool_context in tool_context_history
        )

        tool_catalog = get_tool_catalog()

        tool_definitions = [
            ModelToolDefinition.model_validate(
                tool_entry
            )
            for tool_entry in tool_catalog
        ]

        action_messages = build_action_messages(
            user_message=user_message,
            organization_slug=context.organization_slug,
            tool_catalog=tool_catalog,
            conversation_history=conversation_history,
            tool_context_history=tool_context_mappings,
        )

        action_response = await self._client.generate(
            request=ModelRequest(
                purpose="action_selection",
                messages=action_messages,
                tools=tool_definitions,
                response_format="json_object",
                temperature=0.0,
                max_output_tokens=self._get_output_limit(),
                stream=False,
                metadata={
                    "organization_slug": (
                        context.organization_slug
                    ),
                },
            )
        )

        model_responses: list[ModelResponse] = [
            action_response
        ]

        tool_executions: list[
            ConversationToolExecutionRecord
        ] = []

        prior_protocol_tool_attempts = 0

        initial_attempt_started_at = (
            perf_counter_ns()
        )

        try:
            action_attempt = await self._attempt_action_response(
                response=action_response,
                session=session,
                context=context,
            )

        except ModelProtocolError as initial_error:
            if not initial_error.repairable:
                raise

            initial_attempt_duration_ms = (
                self._elapsed_milliseconds(
                    started_at_ns=(
                        initial_attempt_started_at
                    ),
                )
            )

            initial_protocol_execution = (
                self._build_protocol_execution_record(
                    error=initial_error,
                    attempt_phase="action_selection",
                    execution_order=(
                        len(tool_executions)
                        + 1
                    ),
                    duration_ms=(
                        initial_attempt_duration_ms
                    ),
                )
            )

            if initial_protocol_execution is not None:
                tool_executions.append(
                    initial_protocol_execution
                )

            prior_protocol_tool_attempts = (
                initial_error.attempted_tool_call_count
            )

            repair_messages = build_action_repair_messages(
                user_message=user_message,
                organization_slug=context.organization_slug,
                tool_catalog=tool_catalog,
                previous_output=(
                    self._serialize_response_for_repair(
                        response=action_response,
                    )
                ),
                correction_detail=(
                    str(initial_error)[:2000]
                ),
                conversation_history=conversation_history,
                tool_context_history=tool_context_mappings,
            )

            repair_response = await self._client.generate(
                request=ModelRequest(
                    purpose="action_repair",
                    messages=repair_messages,
                    tools=tool_definitions,
                    response_format="json_object",
                    temperature=0.0,
                    max_output_tokens=self._get_output_limit(),
                    stream=False,
                    metadata={
                        "organization_slug": (
                            context.organization_slug
                        ),
                        "repair_attempt": 1,
                    },
                )
            )

            model_responses.append(
                repair_response
            )

            repair_attempt_started_at = (
                perf_counter_ns()
            )

            try:
                action_attempt = (
                    await self._attempt_action_response(
                        response=repair_response,
                        session=session,
                        context=context,
                    )
                )

            except ModelProtocolError as repair_error:
                repair_attempt_duration_ms = (
                    self._elapsed_milliseconds(
                        started_at_ns=(
                            repair_attempt_started_at
                        ),
                    )
                )

                repair_protocol_execution = (
                    self._build_protocol_execution_record(
                        error=repair_error,
                        attempt_phase="action_repair",
                        execution_order=(
                            len(tool_executions)
                            + 1
                        ),
                        duration_ms=(
                            repair_attempt_duration_ms
                        ),
                    )
                )

                if repair_protocol_execution is not None:
                    tool_executions.append(
                        repair_protocol_execution
                    )

                fallback_action = RespondAction(
                    action="respond",
                    message=_PROTOCOL_FALLBACK_MESSAGE,
                )

                return self._build_turn_result(
                    action=fallback_action,
                    responses=model_responses,
                    tool_call_count=(
                        prior_protocol_tool_attempts
                        + repair_error.attempted_tool_call_count
                    ),
                    successful_tool_call_count=0,
                    tool_executions=tuple(
                        tool_executions
                    ),
                )

            else:
                repair_executions = (
                    self._build_action_attempt_execution_records(
                        action_attempt=action_attempt,
                        attempt_phase="action_repair",
                        starting_execution_order=(
                            len(tool_executions)
                            + 1
                        ),
                    )
                )

                tool_executions.extend(
                    repair_executions
                )

        else:
            initial_executions = (
                self._build_action_attempt_execution_records(
                    action_attempt=action_attempt,
                    attempt_phase="action_selection",
                    starting_execution_order=(
                        len(tool_executions)
                        + 1
                    ),
                )
            )

            tool_executions.extend(
                initial_executions
            )

        total_tool_call_count = (
            prior_protocol_tool_attempts
            + action_attempt.tool_call_count
        )

        if isinstance(
            action_attempt.action,
            RespondAction,
        ):
            return self._build_turn_result(
                action=action_attempt.action,
                responses=model_responses,
                tool_call_count=total_tool_call_count,
                successful_tool_call_count=(
                    action_attempt
                    .successful_tool_call_count
                ),
                tool_executions=tuple(
                    tool_executions
                ),
            )

        if not isinstance(
            action_attempt.action,
            (
                ToolCallAction,
                ToolCallsAction,
            ),
        ):
            raise ConversationOrchestrationError(
                "The model returned an unsupported action."
            )

        batch_result = action_attempt.batch_result

        if batch_result is None:
            raise ConversationOrchestrationError(
                "A tool action did not return a batch result."
            )

        if (
            batch_result.successful_tool_call_count
            == 0
        ):
            clarification_action = RespondAction(
                action="respond",
                message=(
                    "I could not retrieve the requested published "
                    "information. Please verify the department or "
                    "item name and try again."
                ),
            )

            return self._build_turn_result(
                action=clarification_action,
                responses=model_responses,
                tool_call_count=total_tool_call_count,
                successful_tool_call_count=0,
                tool_executions=tuple(
                    tool_executions
                ),
            )

        batch_execution_records = tuple(
            tool_executions[
                -batch_result.tool_call_count:
            ]
        )

        if (
            len(batch_execution_records)
            != batch_result.tool_call_count
        ):
            raise ConversationOrchestrationError(
                "The tool batch did not have a matching "
                "set of audit records."
            )

        synthesis_results: list[
            dict[str, object]
        ] = []

        successful_tool_names: list[str] = []

        successful_tool_results: list[
            ConversationToolResultRecord
        ] = []

        for (
            outcome,
            execution_record,
        ) in zip(
            batch_result.outcomes,
            batch_execution_records,
            strict=True,
        ):
            if (
                outcome.tool_name
                != execution_record.tool_name
            ):
                raise ConversationOrchestrationError(
                    "A tool outcome did not match its "
                    "audit-record tool name."
                )

            if (
                execution_record
                .validated_arguments_json
                is None
            ):
                raise ConversationOrchestrationError(
                    "An executed tool audit did not contain "
                    "validated arguments."
                )

            if (
                dict(
                    outcome.validated_arguments_json
                )
                != dict(
                    execution_record
                    .validated_arguments_json
                )
            ):
                raise ConversationOrchestrationError(
                    "A tool outcome did not match its "
                    "audited validated arguments."
                )

            if not outcome.succeeded:
                if (
                    execution_record.status
                    == "succeeded"
                ):
                    raise ConversationOrchestrationError(
                        "A failed tool outcome had a successful "
                        "audit status."
                    )

                continue

            if (
                execution_record.status
                != "succeeded"
            ):
                raise ConversationOrchestrationError(
                    "A successful tool outcome did not have "
                    "a successful audit status."
                )

            if outcome.result is None:
                raise ConversationOrchestrationError(
                    "A successful tool outcome did not "
                    "contain a result."
                )

            result_json = (
                outcome.result.model_dump(
                    mode="json",
                )
            )

            registered_tool = get_registered_tool(
                tool_name=outcome.tool_name,
            )

            synthesis_results.append(
                {
                    "tool_name": outcome.tool_name,
                    "tool_result": result_json,
                    "presentation_guidance": (
                        registered_tool
                        .presentation_guidance
                    ),
                    "empty_result_guidance": (
                        registered_tool
                        .empty_result_guidance
                    ),
                }
            )

            successful_tool_names.append(
                outcome.tool_name
            )

            successful_tool_results.append(
                ConversationToolResultRecord(
                    execution_order=(
                        execution_record
                        .execution_order
                    ),
                    tool_name=outcome.tool_name,
                    validated_arguments_json=dict(
                        outcome
                        .validated_arguments_json
                    ),
                    result_json=dict(
                        result_json
                    ),
                )
            )

        if not synthesis_results:
            raise ConversationOrchestrationError(
                "No successful tool result was available "
                "for final synthesis."
            )

        result_prompt = build_tool_results_prompt(
            user_message=user_message,
            tool_results=tuple(
                synthesis_results
            ),
        )

        synthesis_request = ModelRequest(
            purpose="tool_result_synthesis",
            messages=[
                ModelMessage(
                    role="user",
                    content=result_prompt,
                ),
            ],
            response_format="text",
            temperature=0.0,
            max_output_tokens=self._get_output_limit(),
            stream=False,
            metadata={
                "organization_slug": (
                    context.organization_slug
                ),
                "tool_names": (
                    successful_tool_names
                ),
                "tool_call_count": (
                    batch_result.tool_call_count
                ),
                "successful_tool_call_count": (
                    batch_result
                    .successful_tool_call_count
                ),
            },
        )

        return _PreparedSynthesisTurn(
            request=synthesis_request,
            model_responses=tuple(
                model_responses
            ),
            tool_call_count=total_tool_call_count,
            successful_tool_call_count=(
                action_attempt
                .successful_tool_call_count
            ),
            tool_executions=tuple(
                tool_executions
            ),
            tool_results=tuple(
                successful_tool_results
            ),
            has_tool_failures=(
                batch_result.has_failures
            ),
        )

    async def _complete_prepared_turn(
        self,
        *,
        prepared_turn: _PreparedSynthesisTurn,
    ) -> ConversationTurnResult:
        """Complete one prepared tool-backed turn without streaming."""

        final_response = await self._client.generate(
            request=prepared_turn.request
        )

        return self._finalize_prepared_turn(
            prepared_turn=prepared_turn,
            final_response=final_response,
        )

    def _finalize_prepared_turn(
        self,
        *,
        prepared_turn: _PreparedSynthesisTurn,
        final_response: ModelResponse,
    ) -> ConversationTurnResult:
        """Build the shared completed result for either delivery mode."""

        model_responses = (
            *prepared_turn.model_responses,
            final_response,
        )

        if final_response.tool_calls:
            raise UnexpectedFollowUpActionError()

        final_message = self._read_final_message(
            response=final_response,
        )

        if prepared_turn.has_tool_failures:
            final_message = (
                f"{final_message}\n\n"
                f"{_PARTIAL_TOOL_FAILURE_MESSAGE}"
            )

        final_action = RespondAction(
            action="respond",
            message=final_message,
        )

        return self._build_turn_result(
            action=final_action,
            responses=model_responses,
            tool_call_count=(
                prepared_turn.tool_call_count
            ),
            successful_tool_call_count=(
                prepared_turn
                .successful_tool_call_count
            ),
            tool_executions=(
                prepared_turn.tool_executions
            ),
            tool_results=(
                prepared_turn.tool_results
            ),
        )

    async def _attempt_action_response(
        self,
        *,
        response: ModelResponse,
        session: AsyncSession,
        context: ToolContext,
    ) -> _ActionAttemptResult:
        """
        Interpret one action response and execute its bounded tool batch.

        ModelProtocolError is intentionally allowed to propagate so the
        caller may perform one bounded correction request.
        """

        model_action = self._response_to_action(
            response=response,
        )

        if isinstance(
            model_action,
            RespondAction,
        ):
            return _ActionAttemptResult(
                action=model_action,
            )

        if not isinstance(
            model_action,
            (
                ToolCallAction,
                ToolCallsAction,
            ),
        ):
            raise ConversationOrchestrationError(
                "The model returned an unsupported action."
            )

        batch_result = await execute_tool_batch(
            action=model_action,
            session=session,
            context=context,
        )

        return _ActionAttemptResult(
            action=model_action,
            batch_result=batch_result,
        )

    def _build_action_attempt_execution_records(
        self,
        *,
        action_attempt: _ActionAttemptResult,
        attempt_phase: ToolExecutionAttemptPhase,
        starting_execution_order: int,
    ) -> tuple[
        ConversationToolExecutionRecord,
        ...
    ]:
        """Create ordered audit records from one completed action."""

        batch_result = action_attempt.batch_result

        if batch_result is None:
            if action_attempt.tool_call_count != 0:
                raise ConversationOrchestrationError(
                    "An action without a batch result reported "
                    "tool calls."
                )

            if (
                action_attempt
                .successful_tool_call_count
                != 0
            ):
                raise ConversationOrchestrationError(
                    "An action without a batch result reported "
                    "successful tool calls."
                )

            return ()

        if not isinstance(
            action_attempt.action,
            (
                ToolCallAction,
                ToolCallsAction,
            ),
        ):
            raise ConversationOrchestrationError(
                "A tool batch was attached to a non-tool action."
            )

        if (
            batch_result.tool_call_count
            != len(batch_result.outcomes)
        ):
            raise ConversationOrchestrationError(
                "Tool-batch counts did not match its outcomes."
            )

        records: list[
            ConversationToolExecutionRecord
        ] = []

        for offset, outcome in enumerate(
            batch_result.outcomes
        ):
            if outcome.succeeded:
                if outcome.result is None:
                    raise ConversationOrchestrationError(
                        "A successful tool outcome did not "
                        "contain a result."
                    )

                if outcome.error is not None:
                    raise ConversationOrchestrationError(
                        "A successful tool outcome contained "
                        "an error."
                    )

                status = "succeeded"
                failure_category = None

            else:
                if outcome.error is None:
                    raise ConversationOrchestrationError(
                        "A failed tool outcome did not "
                        "contain an error."
                    )

                status = "execution_failed"

                failure_category = (
                    outcome.failure_category
                    or "tool_execution_failed"
                )

            records.append(
                ConversationToolExecutionRecord(
                    execution_order=(
                        starting_execution_order
                        + offset
                    ),
                    attempt_phase=attempt_phase,
                    tool_name=outcome.tool_name,
                    validated_arguments_json=dict(
                        outcome
                        .validated_arguments_json
                    ),
                    status=status,
                    failure_category=(
                        failure_category
                    ),
                    duration_ms=(
                        outcome.duration_ms
                    ),
                )
            )

        recorded_successes = sum(
            1
            for record in records
            if record.status == "succeeded"
        )

        if (
            recorded_successes
            != batch_result
            .successful_tool_call_count
        ):
            raise ConversationOrchestrationError(
                "Tool-batch audit records did not match "
                "the successful-call count."
            )

        return tuple(
            records
        )

    def _build_protocol_execution_record(
        self,
        *,
        error: ModelProtocolError,
        attempt_phase: ToolExecutionAttemptPhase,
        execution_order: int,
        duration_ms: int,
    ) -> ConversationToolExecutionRecord | None:
        """Create an audit record for a counted protocol failure."""

        if error.attempted_tool_call_count == 0:
            return None

        if error.attempted_tool_call_count != 1:
            raise ConversationOrchestrationError(
                "A counted protocol error did not expose one "
                "auditable tool attempt."
            )

        if isinstance(
            error,
            UnknownToolError,
        ):
            return ConversationToolExecutionRecord(
                execution_order=execution_order,
                attempt_phase=attempt_phase,
                tool_name=error.tool_name,
                validated_arguments_json=None,
                status="unknown_tool",
                failure_category="tool_not_registered",
                duration_ms=duration_ms,
            )

        if isinstance(
            error,
            InvalidToolArgumentsError,
        ):
            return ConversationToolExecutionRecord(
                execution_order=execution_order,
                attempt_phase=attempt_phase,
                tool_name=error.tool_name,
                validated_arguments_json=None,
                status="arguments_rejected",
                failure_category="invalid_tool_arguments",
                duration_ms=duration_ms,
            )

        raise ConversationOrchestrationError(
            "A counted protocol error did not expose safe "
            "tool-audit metadata."
        )

    def _response_to_action(
        self,
        *,
        response: ModelResponse,
    ) -> (
        ToolCallAction
        | ToolCallsAction
        | RespondAction
    ):
        """
        Convert normalized native calls or structured JSON text into
        NORA's validated action contract.
        """

        if response.tool_calls:
            if (
                len(response.tool_calls)
                > MAX_TOOL_CALLS_PER_ACTION
            ):
                raise ConversationOrchestrationError(
                    "The model returned more native tool calls "
                    "than the backend permits."
                )

            if len(response.tool_calls) == 1:
                tool_call = response.tool_calls[0]

                return ToolCallAction(
                    action="tool_call",
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                )

            return ToolCallsAction(
                action="tool_calls",
                calls=[
                    {
                        "tool_name": (
                            tool_call.tool_name
                        ),
                        "arguments": (
                            tool_call.arguments
                        ),
                    }
                    for tool_call in response.tool_calls
                ],
            )

        if response.text is None:
            raise ConversationOrchestrationError(
                "The model response did not contain text or "
                "a tool call."
            )

        return parse_model_action(
            raw_output=response.text,
        )

    def _serialize_response_for_repair(
        self,
        *,
        response: ModelResponse,
    ) -> str:
        """Return a bounded representation of the unusable response."""

        if response.tool_calls:
            serialized_response = json.dumps(
                {
                    "text": response.text,
                    "tool_calls": [
                        tool_call.model_dump(
                            mode="json",
                        )
                        for tool_call in response.tool_calls
                    ],
                },
                indent=2,
                default=str,
            )
        else:
            serialized_response = (
                response.text
                or ""
            )

        return serialized_response[:8000]

    def _read_final_message(
        self,
        *,
        response: ModelResponse,
    ) -> str:
        """Return validated plain text from the final synthesis phase."""

        if response.tool_calls:
            raise UnexpectedFollowUpActionError()

        if response.text is None:
            raise ConversationOrchestrationError(
                "The final model response did not contain text."
            )

        final_message = response.text.strip()

        if not final_message:
            raise ConversationOrchestrationError(
                "The final model response was empty."
            )

        return final_message

    def _build_turn_result(
        self,
        *,
        action: RespondAction,
        responses: Sequence[ModelResponse],
        tool_call_count: int = 0,
        successful_tool_call_count: int = 0,
        tool_executions: tuple[
            ConversationToolExecutionRecord,
            ...
        ] = (),
        tool_results: tuple[
            ConversationToolResultRecord,
            ...
        ] = (),
    ) -> ConversationTurnResult:
        """Build the final result returned for one conversation turn."""

        if tool_call_count != len(
            tool_executions
        ):
            raise ConversationOrchestrationError(
                "Tool execution records do not match the "
                "aggregate tool-call count."
            )

        recorded_successful_tool_calls = sum(
            1
            for execution in tool_executions
            if execution.status == "succeeded"
        )

        if (
            successful_tool_call_count
            != recorded_successful_tool_calls
        ):
            raise ConversationOrchestrationError(
                "Successful tool execution records do not "
                "match the aggregate success count."
            )

        if (
            successful_tool_call_count
            != len(tool_results)
        ):
            raise ConversationOrchestrationError(
                "Successful tool results do not match "
                "the aggregate success count."
            )

        successful_execution_records = tuple(
            execution
            for execution in tool_executions
            if execution.status == "succeeded"
        )

        result_execution_orders = tuple(
            tool_result.execution_order
            for tool_result in tool_results
        )

        expected_result_execution_orders = tuple(
            execution.execution_order
            for execution in successful_execution_records
        )

        if (
            result_execution_orders
            != expected_result_execution_orders
        ):
            raise ConversationOrchestrationError(
                "Successful tool results are not aligned "
                "with successful execution records."
            )

        for (
            tool_result,
            execution_record,
        ) in zip(
            tool_results,
            successful_execution_records,
            strict=True,
        ):
            if (
                tool_result.tool_name
                != execution_record.tool_name
            ):
                raise ConversationOrchestrationError(
                    "A successful tool result did not match "
                    "its execution-record tool name."
                )

            if (
                execution_record
                .validated_arguments_json
                is None
            ):
                raise ConversationOrchestrationError(
                    "A successful execution record did not "
                    "contain validated arguments."
                )

            if (
                tool_result
                .validated_arguments_json
                != execution_record
                .validated_arguments_json
            ):
                raise ConversationOrchestrationError(
                    "A successful tool result did not match "
                    "its execution-record arguments."
                )

        expected_execution_orders = tuple(
            range(
                1,
                len(tool_executions) + 1,
            )
        )

        actual_execution_orders = tuple(
            execution.execution_order
            for execution in tool_executions
        )

        if (
            actual_execution_orders
            != expected_execution_orders
        ):
            raise ConversationOrchestrationError(
                "Tool execution records are not in contiguous "
                "chronological order."
            )

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
            tool_executions=tool_executions,
            tool_results=tool_results,
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

    def _elapsed_milliseconds(
        self,
        *,
        started_at_ns: int,
    ) -> int:
        """Return nonnegative elapsed whole milliseconds."""

        elapsed_nanoseconds = (
            perf_counter_ns()
            - started_at_ns
        )

        return max(
            0,
            elapsed_nanoseconds
            // 1_000_000,
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