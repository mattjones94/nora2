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

from app.llm.errors import (
    InvalidActionEnvelopeError,
    InvalidModelActionError,
    MalformedActionJsonError,
    ModelActionError,
)
from app.llm.tool_registry import (
    RegisteredToolExecutionResult,
    execute_registered_tool,
)
from app.tools.context import ToolContext


MAX_TOOL_CALLS_PER_ACTION = 3


class ToolCallRequest(BaseModel):
    """One provider-neutral registered-tool request."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    tool_name: str = Field(
        min_length=1,
        max_length=100,
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict,
    )


class ToolCallAction(
    ToolCallRequest
):
    """A request from the model to execute one registered tool."""

    action: Literal["tool_call"]


class ToolCallsAction(BaseModel):
    """An ordered bounded sequence of registered-tool requests."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    action: Literal["tool_calls"]

    calls: list[ToolCallRequest] = Field(
        min_length=2,
        max_length=MAX_TOOL_CALLS_PER_ACTION,
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
    (
        ToolCallAction
        | ToolCallsAction
        | RespondAction
    ),
    Field(
        discriminator="action"
    ),
]

_model_action_adapter = TypeAdapter(
    ModelAction
)


def parse_model_action(
    raw_output: str | Mapping[str, Any],
) -> (
    ToolCallAction
    | ToolCallsAction
    | RespondAction
):
    """
    Parse, safely normalize, and validate model action output.

    A structurally clean tool_calls envelope containing exactly one
    request is normalized into the equivalent tool_call action. Empty,
    oversized, malformed, and otherwise invalid batches remain invalid.
    """

    if isinstance(raw_output, str):
        parsed_output = _parse_action_json(
            raw_output=raw_output,
        )
    else:
        parsed_output = dict(
            raw_output
        )

    parsed_output = (
        _normalize_single_call_batch(
            parsed_output=parsed_output,
        )
    )

    try:
        return _model_action_adapter.validate_python(
            parsed_output
        )
    except ValidationError as error:
        raise InvalidActionEnvelopeError(
            detail=_format_validation_error(
                error
            )
        ) from error


def _normalize_single_call_batch(
    *,
    parsed_output: Any,
) -> Any:
    """
    Normalize one clean batched request into the single-call contract.

    Normalization occurs only when the outer envelope and inner call
    contain no unexpected fields. Invalid structures are returned
    unchanged so normal Pydantic validation can reject them.
    """

    if not isinstance(
        parsed_output,
        Mapping,
    ):
        return parsed_output

    if (
        parsed_output.get("action")
        != "tool_calls"
    ):
        return parsed_output

    if set(
        parsed_output.keys()
    ) != {
        "action",
        "calls",
    }:
        return parsed_output

    raw_calls = parsed_output.get(
        "calls"
    )

    if (
        not isinstance(
            raw_calls,
            list,
        )
        or len(raw_calls) != 1
    ):
        return parsed_output

    raw_call = raw_calls[0]

    if not isinstance(
        raw_call,
        Mapping,
    ):
        return parsed_output

    call_fields = set(
        raw_call.keys()
    )

    allowed_call_fields = {
        "tool_name",
        "arguments",
    }

    if (
        "tool_name"
        not in call_fields
        or not call_fields.issubset(
            allowed_call_fields
        )
    ):
        return parsed_output

    normalized_action: dict[
        str,
        Any,
    ] = {
        "action": "tool_call",
        "tool_name": raw_call[
            "tool_name"
        ],
    }

    if "arguments" in raw_call:
        normalized_action[
            "arguments"
        ] = raw_call[
            "arguments"
        ]

    return normalized_action


def _parse_action_json(
    *,
    raw_output: str,
) -> Any:
    """
    Parse strict JSON or one complete Markdown JSON fence.

    Nora deliberately does not search prose for an embedded JSON
    substring because doing so could accept unintended model output.
    """

    normalized_output = raw_output.strip()

    try:
        return json.loads(
            normalized_output
        )
    except json.JSONDecodeError as strict_error:
        fenced_output = _unwrap_single_json_fence(
            raw_output=normalized_output,
        )

        if fenced_output is None:
            raise MalformedActionJsonError(
                detail=strict_error.msg,
            ) from strict_error

        try:
            return json.loads(
                fenced_output
            )
        except json.JSONDecodeError as fenced_error:
            raise MalformedActionJsonError(
                detail=fenced_error.msg,
            ) from fenced_error


def _unwrap_single_json_fence(
    *,
    raw_output: str,
) -> str | None:
    """Return the contents of one full-response JSON fence."""

    lines = raw_output.splitlines()

    if len(lines) < 3:
        return None

    opening_fence = (
        lines[0]
        .strip()
        .lower()
    )

    closing_fence = (
        lines[-1]
        .strip()
    )

    if opening_fence not in {
        "```",
        "```json",
    }:
        return None

    if closing_fence != "```":
        return None

    fenced_content = "\n".join(
        lines[1:-1]
    ).strip()

    if not fenced_content:
        return None

    return fenced_content


def _format_validation_error(
    error: ValidationError,
) -> str:
    """Return validation details without echoing raw model input."""

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
            location = "action"

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
        return "The action structure was invalid."

    return "; ".join(
        details
    )


async def execute_tool_call_action(
    *,
    action: ToolCallAction | ToolCallRequest,
    session: AsyncSession,
    context: ToolContext,
) -> RegisteredToolExecutionResult:
    """Execute one validated tool request using trusted backend context."""

    return await execute_registered_tool(
        tool_name=action.tool_name,
        raw_arguments=action.arguments,
        session=session,
        context=context,
    )