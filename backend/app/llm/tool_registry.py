from collections.abc import (
    Awaitable,
    Callable,
    Mapping,
)
from dataclasses import dataclass
from typing import Any

from pydantic import (
    BaseModel,
    ValidationError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.errors import (
    InvalidToolArgumentsError,
    UnknownToolError,
)
from app.tools.context import ToolContext
from app.tools.departments.get_department_details import (
    GetDepartmentDetailsArguments,
    GetDepartmentDetailsResult,
    TOOL_DESCRIPTION as DEPARTMENT_DETAILS_DESCRIPTION,
    TOOL_EMPTY_RESULT_GUIDANCE as DEPARTMENT_DETAILS_EMPTY_RESULT_GUIDANCE,
    TOOL_NAME as DEPARTMENT_DETAILS_NAME,
    TOOL_PRESENTATION_GUIDANCE as DEPARTMENT_DETAILS_PRESENTATION_GUIDANCE,
    get_department_details,
)
from app.tools.departments.list_departments import (
    ListDepartmentsArguments,
    ListDepartmentsResult,
    TOOL_DESCRIPTION as DEPARTMENTS_DESCRIPTION,
    TOOL_EMPTY_RESULT_GUIDANCE as DEPARTMENTS_EMPTY_RESULT_GUIDANCE,
    TOOL_NAME as DEPARTMENTS_NAME,
    TOOL_PRESENTATION_GUIDANCE as DEPARTMENTS_PRESENTATION_GUIDANCE,
    list_departments,
)
from app.tools.errors import ToolExecutionError
from app.tools.events.get_upcoming_events import (
    GetUpcomingEventsArguments,
    GetUpcomingEventsResult,
    TOOL_DESCRIPTION as UPCOMING_EVENTS_DESCRIPTION,
    TOOL_EMPTY_RESULT_GUIDANCE as UPCOMING_EVENTS_EMPTY_RESULT_GUIDANCE,
    TOOL_NAME as UPCOMING_EVENTS_NAME,
    TOOL_PRESENTATION_GUIDANCE as UPCOMING_EVENTS_PRESENTATION_GUIDANCE,
    get_upcoming_events,
)


ToolExecutor = Callable[
    ...,
    Awaitable[BaseModel],
]


@dataclass(
    frozen=True,
    slots=True,
)
class RegisteredTool:
    """Definition of one controlled tool available to the LLM runtime."""

    name: str
    description: str
    argument_model: type[BaseModel]
    result_model: type[BaseModel]
    executor: ToolExecutor
    presentation_guidance: tuple[str, ...] = ()
    empty_result_guidance: str | None = None

    def catalog_entry(self) -> dict[str, Any]:
        """Return a model-independent description of the tool."""

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": (
                self.argument_model.model_json_schema()
            ),
        }


@dataclass(
    frozen=True,
    slots=True,
)
class PreparedRegisteredToolCall:
    """
    One registered tool call whose name and arguments are validated.

    Preparing a call performs no tool execution and no database work.
    """

    tool: RegisteredTool

    validated_arguments: BaseModel

    validated_arguments_json: dict[str, Any]


@dataclass(
    frozen=True,
    slots=True,
)
class RegisteredToolExecutionResult:
    """Validated metadata and result from one registered tool call."""

    tool_name: str

    validated_arguments_json: dict[str, Any]

    result: BaseModel


class RegisteredToolExecutionError(
    ToolExecutionError
):
    """
    Expected registered-tool failure with safe execution metadata.

    The original feature error remains available through exception
    chaining but is not intended for persistence.
    """

    def __init__(
        self,
        *,
        tool_name: str,
        validated_arguments_json: dict[str, Any],
        failure_category: str,
        detail: str,
    ) -> None:
        self.tool_name = tool_name
        self.validated_arguments_json = (
            validated_arguments_json
        )
        self.failure_category = failure_category

        super().__init__(
            detail
        )


class ToolNotRegisteredError(
    UnknownToolError
):
    """
    Backward-compatible registry-specific unknown-tool error.

    It is also a ModelProtocolError through UnknownToolError.
    """


_TOOL_REGISTRY: dict[str, RegisteredTool] = {
    DEPARTMENTS_NAME: RegisteredTool(
        name=DEPARTMENTS_NAME,
        description=DEPARTMENTS_DESCRIPTION,
        argument_model=ListDepartmentsArguments,
        result_model=ListDepartmentsResult,
        executor=list_departments,
        presentation_guidance=(
            DEPARTMENTS_PRESENTATION_GUIDANCE
        ),
        empty_result_guidance=(
            DEPARTMENTS_EMPTY_RESULT_GUIDANCE
        ),
    ),
    DEPARTMENT_DETAILS_NAME: RegisteredTool(
        name=DEPARTMENT_DETAILS_NAME,
        description=DEPARTMENT_DETAILS_DESCRIPTION,
        argument_model=GetDepartmentDetailsArguments,
        result_model=GetDepartmentDetailsResult,
        executor=get_department_details,
        presentation_guidance=(
            DEPARTMENT_DETAILS_PRESENTATION_GUIDANCE
        ),
        empty_result_guidance=(
            DEPARTMENT_DETAILS_EMPTY_RESULT_GUIDANCE
        ),
    ),
    UPCOMING_EVENTS_NAME: RegisteredTool(
        name=UPCOMING_EVENTS_NAME,
        description=UPCOMING_EVENTS_DESCRIPTION,
        argument_model=GetUpcomingEventsArguments,
        result_model=GetUpcomingEventsResult,
        executor=get_upcoming_events,
        presentation_guidance=(
            UPCOMING_EVENTS_PRESENTATION_GUIDANCE
        ),
        empty_result_guidance=(
            UPCOMING_EVENTS_EMPTY_RESULT_GUIDANCE
        ),
    ),
}


def list_registered_tools() -> list[RegisteredTool]:
    """Return all tools currently available to the LLM runtime."""

    return list(
        _TOOL_REGISTRY.values()
    )


def get_tool_catalog() -> list[dict[str, Any]]:
    """Return tool definitions suitable for prompts or adapters."""

    return [
        tool.catalog_entry()
        for tool in list_registered_tools()
    ]


def get_registered_tool(
    tool_name: str,
) -> RegisteredTool:
    """Find a registered tool by its exact name."""

    tool = _TOOL_REGISTRY.get(
        tool_name
    )

    if tool is None:
        raise ToolNotRegisteredError(
            tool_name=tool_name,
        )

    return tool


def prepare_registered_tool_call(
    *,
    tool_name: str,
    raw_arguments: Mapping[str, Any],
) -> PreparedRegisteredToolCall:
    """
    Resolve one registered tool and validate its arguments.

    No executor is called during preparation. This allows an entire
    bounded batch to be validated before any tool begins executing.
    """

    tool = get_registered_tool(
        tool_name=tool_name,
    )

    try:
        validated_arguments = (
            tool.argument_model.model_validate(
                dict(raw_arguments)
            )
        )
    except ValidationError as error:
        raise InvalidToolArgumentsError(
            tool_name=tool_name,
            detail=_format_argument_validation_error(
                error
            ),
        ) from error

    validated_arguments_json = (
        validated_arguments.model_dump(
            mode="json",
        )
    )

    return PreparedRegisteredToolCall(
        tool=tool,
        validated_arguments=validated_arguments,
        validated_arguments_json=(
            validated_arguments_json
        ),
    )


async def execute_prepared_registered_tool(
    *,
    prepared_call: PreparedRegisteredToolCall,
    session: AsyncSession,
    context: ToolContext,
) -> RegisteredToolExecutionResult:
    """
    Execute one previously validated registered-tool call.

    Expected feature-level failures retain the safe validated
    arguments and bounded failure category.
    """

    tool = prepared_call.tool

    try:
        execution_result = await tool.executor(
            session=session,
            context=context,
            arguments=(
                prepared_call.validated_arguments
            ),
        )

    except ToolExecutionError as error:
        raise RegisteredToolExecutionError(
            tool_name=tool.name,
            validated_arguments_json=(
                prepared_call.validated_arguments_json
            ),
            failure_category=error.failure_category,
            detail=str(error),
        ) from error

    result_payload = execution_result.model_dump(
        mode="python",
    )

    validated_result = (
        tool.result_model.model_validate(
            result_payload
        )
    )

    return RegisteredToolExecutionResult(
        tool_name=tool.name,
        validated_arguments_json=(
            prepared_call.validated_arguments_json
        ),
        result=validated_result,
    )


async def execute_registered_tool(
    *,
    tool_name: str,
    raw_arguments: Mapping[str, Any],
    session: AsyncSession,
    context: ToolContext,
) -> RegisteredToolExecutionResult:
    """
    Validate and execute one registered tool.

    This compatibility entry point composes the separate preparation
    and execution boundaries used by the future batch orchestrator.
    """

    prepared_call = prepare_registered_tool_call(
        tool_name=tool_name,
        raw_arguments=raw_arguments,
    )

    return await execute_prepared_registered_tool(
        prepared_call=prepared_call,
        session=session,
        context=context,
    )


def _format_argument_validation_error(
    error: ValidationError,
) -> str:
    """Return safe tool-argument validation details."""

    details: list[str] = []

    for issue in error.errors(
        include_url=False,
        include_input=False,
    ):
        location = ".".join(
            str(part)
            for part in issue.get(
                "loc",
                (),
            )
        )

        if not location:
            location = "arguments"

        message = str(
            issue.get(
                "msg",
                "invalid value",
            )
        )

        details.append(
            f"{location}: {message}"
        )

    if not details:
        return "The supplied tool arguments were invalid."

    return "; ".join(
        details
    )