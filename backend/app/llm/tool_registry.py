from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.context import ToolContext


#tool imports for events

from app.tools.events.get_upcoming_events import (
    GetUpcomingEventsArguments,
    TOOL_DESCRIPTION as UPCOMING_EVENTS_DESCRIPTION,
    TOOL_NAME as UPCOMING_EVENTS_NAME,
    get_upcoming_events,
)

#tools for department imports

from app.tools.departments.list_departments import (
    ListDepartmentsArguments,
    TOOL_DESCRIPTION as DEPARTMENTS_DESCRIPTION,
    TOOL_NAME as DEPARTMENTS_NAME,
    list_departments,
)

from app.tools.departments.get_department_details import (
    GetDepartmentDetailsArguments,
    TOOL_DESCRIPTION as DEPARTMENT_DETAILS_DESCRIPTION,
    TOOL_NAME as DEPARTMENT_DETAILS_NAME,
    get_department_details,
)

ToolExecutor = Callable[..., Awaitable[BaseModel]]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    """Definition of one controlled tool available to the LLM runtime."""

    name: str
    description: str
    argument_model: type[BaseModel]
    executor: ToolExecutor

    def catalog_entry(self) -> dict[str, Any]:
        """Return a model-independent description of the tool."""

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.argument_model.model_json_schema(),
        }


class ToolNotRegisteredError(Exception):
    """Raised when the model requests an unavailable tool."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' is not registered."
        )


_TOOL_REGISTRY: dict[str, RegisteredTool] = {
    DEPARTMENTS_NAME: RegisteredTool(
        name=DEPARTMENTS_NAME,
        description=DEPARTMENTS_DESCRIPTION,
        argument_model=ListDepartmentsArguments,
        executor=list_departments,
    ),
    DEPARTMENT_DETAILS_NAME: RegisteredTool(
        name=DEPARTMENT_DETAILS_NAME,
        description=DEPARTMENT_DETAILS_DESCRIPTION,
        argument_model=GetDepartmentDetailsArguments,
        executor=get_department_details,
    ),
    UPCOMING_EVENTS_NAME: RegisteredTool(
        name=UPCOMING_EVENTS_NAME,
        description=UPCOMING_EVENTS_DESCRIPTION,
        argument_model=GetUpcomingEventsArguments,
        executor=get_upcoming_events,
    ),
}


def list_registered_tools() -> list[RegisteredTool]:
    """Return all tools currently available to the LLM runtime."""

    return list(_TOOL_REGISTRY.values())


def get_tool_catalog() -> list[dict[str, Any]]:
    """Return tool definitions suitable for prompts or model adapters."""

    return [
        tool.catalog_entry()
        for tool in list_registered_tools()
    ]


def get_registered_tool(
    tool_name: str,
) -> RegisteredTool:
    """Find a registered tool by its exact name."""

    tool = _TOOL_REGISTRY.get(tool_name)

    if tool is None:
        raise ToolNotRegisteredError(
            tool_name=tool_name,
        )

    return tool


async def execute_registered_tool(
    *,
    tool_name: str,
    raw_arguments: Mapping[str, Any],
    session: AsyncSession,
    context: ToolContext,
) -> BaseModel:
    """Validate and execute a tool using trusted backend context."""

    tool = get_registered_tool(
        tool_name=tool_name,
    )

    validated_arguments = tool.argument_model.model_validate(
        dict(raw_arguments)
    )

    return await tool.executor(
        session=session,
        context=context,
        arguments=validated_arguments,
    )