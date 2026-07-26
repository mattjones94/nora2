import json
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.tool_registry import execute_registered_tool
from app.tools.context import ToolContext


class ModelActionError(Exception):
    """Base error for invalid or unsupported model actions."""


class InvalidModelActionError(ModelActionError):
    """Raised when model output does not match the action contract."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            f"Invalid model action: {detail}"
        )


class ToolCallAction(BaseModel):
    """A request from the model to execute one registered tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    action: Literal["tool_call"]

    tool_name: str = Field(
        min_length=1,
        max_length=100,
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict,
    )


class RespondAction(BaseModel):
    """A direct conversational response that requires no tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    action: Literal["respond"]

    message: str = Field(
        min_length=1,
        max_length=8000,
    )


ModelAction = Annotated[
    ToolCallAction | RespondAction,
    Field(discriminator="action"),
]

_model_action_adapter = TypeAdapter(ModelAction)


def parse_model_action(
    raw_output: str | Mapping[str, Any],
) -> ToolCallAction | RespondAction:
    """Parse and validate structured output produced by the model."""

    if isinstance(raw_output, str):
        try:
            parsed_output = json.loads(raw_output)
        except json.JSONDecodeError as error:
            raise InvalidModelActionError(
                detail=f"Output was not valid JSON: {error.msg}"
            ) from error
    else:
        parsed_output = dict(raw_output)

    try:
        return _model_action_adapter.validate_python(
            parsed_output
        )
    except ValidationError as error:
        raise InvalidModelActionError(
            detail=str(error)
        ) from error


async def execute_tool_call_action(
    *,
    action: ToolCallAction,
    session: AsyncSession,
    context: ToolContext,
) -> BaseModel:
    """Execute a validated tool call using trusted backend context."""

    return await execute_registered_tool(
        tool_name=action.tool_name,
        raw_arguments=action.arguments,
        session=session,
        context=context,
    )