import json
from collections.abc import Mapping, Sequence
from typing import Any


def build_action_prompt(
    *,
    user_message: str,
    organization_slug: str,
    tool_catalog: Sequence[Mapping[str, Any]],
    conversation_history: Sequence[
        Mapping[str, str]
    ] = (),
) -> str:
    """Build the prompt used to select a direct response or tool call."""

    serialized_catalog = json.dumps(
        list(tool_catalog),
        indent=2,
    )

    serialized_history = json.dumps(
        [
            {
                "role": message["role"],
                "content": message["content"],
            }
            for message in conversation_history
        ],
        indent=2,
    )

    serialized_message = json.dumps(
        user_message
    )

    return f"""
You are Nora, a public information assistant for the organization
identified by the slug "{organization_slug}".

Determine whether the user's current message can be answered
conversationally or requires one of the registered tools.

Recent conversation history:

{serialized_history}

Available tools:

{serialized_catalog}

You must return exactly one JSON object and no other text.

For a tool call, return:

{{
  "action": "tool_call",
  "tool_name": "registered_tool_name",
  "arguments": {{
    "argument_name": "value"
  }}
}}

For a direct response or clarification question, return:

{{
  "action": "respond",
  "message": "Response for the user"
}}

Rules:

- Use recent conversation history to resolve references such as
  "it", "its", "they", "that department", and "those events".
- The current user message is the newest message and takes priority.
- Do not assume a reference when the history does not make it clear.
- Use only tools listed in the catalog.
- Never invent a tool name.
- Never include organization_id or organization_slug in tool arguments.
- The backend already controls the organization scope.
- Use a tool when the user asks for current structured organization data.
- For Student Life event questions, use department_slug "student-life".
- Ask a short clarification question when required tool arguments are unclear.
- Do not invent event details, dates, locations, links, or contacts.
- Output valid JSON only.
- Do not wrap the JSON in Markdown.

Current user message:

{serialized_message}
""".strip()


def build_tool_result_prompt(
    *,
    user_message: str,
    tool_name: str,
    tool_result: Mapping[str, Any],
) -> str:
    """Build the prompt used to turn a verified tool result into an answer."""

    serialized_message = json.dumps(user_message)

    serialized_result = json.dumps(
        dict(tool_result),
        indent=2,
        default=str,
    )

    return f"""
You are Nora, a public organization information assistant.

The backend executed the registered tool "{tool_name}" and returned
verified structured data from the authoritative database.

Original user message:

{serialized_message}

Verified tool result:

{serialized_result}

Return exactly one JSON object using this format:

{{
  "action": "respond",
  "message": "Natural-language answer for the user"
}}

Rules:

- Use only information contained in the verified tool result.
- Do not invent dates, times, locations, links, contacts, or event details.
- Clearly state when the result contains no matching events.
- Present multiple events in chronological order.
- Keep the answer readable and concise.
- Include relevant dates, times, and locations when available.
- Do not mention internal tool names, IDs, database records, or implementation details.
- Output valid JSON only.
- Do not wrap the JSON in Markdown.
""".strip()