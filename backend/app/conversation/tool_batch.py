from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.tool_calling import (
    ToolCallAction,
    ToolCallRequest,
    ToolCallsAction,
)
from app.llm.tool_registry import (
    PreparedRegisteredToolCall,
    RegisteredToolExecutionError,
    execute_prepared_registered_tool,
    prepare_registered_tool_call,
)
from app.tools.context import ToolContext
from app.tools.errors import ToolExecutionError


class ToolBatchError(Exception):
    """Base error raised while handling a bounded tool batch."""


class UnsupportedToolBatchActionError(
    ToolBatchError
):
    """Raised when an action cannot be normalized into tool calls."""

    def __init__(self) -> None:
        super().__init__(
            "The action did not contain a supported "
            "tool-call request."
        )


@dataclass(
    frozen=True,
    slots=True,
)
class ToolBatchExecutionOutcome:
    """Result of executing one prepared call within an ordered batch."""

    tool_name: str

    validated_arguments_json: dict[
        str,
        Any,
    ]

    result: BaseModel | None = None
    error: ToolExecutionError | None = None

    failure_category: str | None = None

    duration_ms: int = 0

    @property
    def succeeded(self) -> bool:
        """Return whether this individual call completed successfully."""

        return (
            self.result is not None
            and self.error is None
        )


@dataclass(
    frozen=True,
    slots=True,
)
class ToolBatchExecutionResult:
    """Ordered outcomes from one fully prepared tool-call action."""

    outcomes: tuple[
        ToolBatchExecutionOutcome,
        ...
    ]

    @property
    def tool_call_count(self) -> int:
        """Return the number of executed calls."""

        return len(
            self.outcomes
        )

    @property
    def successful_tool_call_count(self) -> int:
        """Return the number of successful calls."""

        return sum(
            1
            for outcome in self.outcomes
            if outcome.succeeded
        )

    @property
    def has_failures(self) -> bool:
        """Return whether any executed call failed."""

        return any(
            not outcome.succeeded
            for outcome in self.outcomes
        )


def normalize_action_tool_requests(
    *,
    action: ToolCallAction | ToolCallsAction,
) -> tuple[
    ToolCallRequest,
    ...
]:
    """Normalize a single call or batch into one ordered tuple."""

    if isinstance(
        action,
        ToolCallAction,
    ):
        return (
            ToolCallRequest(
                tool_name=action.tool_name,
                arguments=dict(
                    action.arguments
                ),
            ),
        )

    if isinstance(
        action,
        ToolCallsAction,
    ):
        return tuple(
            action.calls
        )

    raise UnsupportedToolBatchActionError()


def prepare_tool_batch(
    *,
    action: ToolCallAction | ToolCallsAction,
) -> tuple[
    PreparedRegisteredToolCall,
    ...
]:
    """
    Validate every call before any executor begins.

    Unknown tools and invalid arguments propagate as protocol errors.
    If any preparation fails, this function returns no partial batch.
    """

    requests = normalize_action_tool_requests(
        action=action,
    )

    prepared_calls: list[
        PreparedRegisteredToolCall
    ] = []

    for request in requests:
        prepared_calls.append(
            prepare_registered_tool_call(
                tool_name=request.tool_name,
                raw_arguments=request.arguments,
            )
        )

    return tuple(
        prepared_calls
    )


async def execute_tool_batch(
    *,
    action: ToolCallAction | ToolCallsAction,
    session: AsyncSession,
    context: ToolContext,
) -> ToolBatchExecutionResult:
    """
    Prepare all calls and then execute them sequentially.

    Preparation errors occur before any executor starts. Expected
    feature-level execution failures are captured as ordered outcomes,
    and later prepared calls are still executed.
    """

    prepared_calls = prepare_tool_batch(
        action=action,
    )

    outcomes: list[
        ToolBatchExecutionOutcome
    ] = []

    for prepared_call in prepared_calls:
        started_at_ns = perf_counter_ns()

        try:
            execution = (
                await execute_prepared_registered_tool(
                    prepared_call=prepared_call,
                    session=session,
                    context=context,
                )
            )

        except RegisteredToolExecutionError as error:
            outcomes.append(
                ToolBatchExecutionOutcome(
                    tool_name=error.tool_name,
                    validated_arguments_json=dict(
                        error.validated_arguments_json
                    ),
                    error=error,
                    failure_category=(
                        error.failure_category
                    ),
                    duration_ms=_elapsed_milliseconds(
                        started_at_ns=started_at_ns,
                    ),
                )
            )

        except ToolExecutionError as error:
            outcomes.append(
                ToolBatchExecutionOutcome(
                    tool_name=(
                        prepared_call.tool.name
                    ),
                    validated_arguments_json=dict(
                        prepared_call
                        .validated_arguments_json
                    ),
                    error=error,
                    failure_category=(
                        error.failure_category
                    ),
                    duration_ms=_elapsed_milliseconds(
                        started_at_ns=started_at_ns,
                    ),
                )
            )

        else:
            outcomes.append(
                ToolBatchExecutionOutcome(
                    tool_name=execution.tool_name,
                    validated_arguments_json=dict(
                        execution
                        .validated_arguments_json
                    ),
                    result=execution.result,
                    duration_ms=_elapsed_milliseconds(
                        started_at_ns=started_at_ns,
                    ),
                )
            )

    return ToolBatchExecutionResult(
        outcomes=tuple(
            outcomes
        )
    )


def _elapsed_milliseconds(
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