import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.llm.contracts import ModelMessage
from app.llm.tool_calling import (
    MAX_TOOL_CALLS_PER_ACTION,
)


def build_action_messages(
    *,
    user_message: str,
    organization_slug: str,
    tool_catalog: Sequence[Mapping[str, Any]],
    conversation_history: Sequence[
        Mapping[str, str]
    ] = (),
) -> list[ModelMessage]:
    """Build messages used to select a response or bounded tool action."""

    serialized_catalog = json.dumps(
        list(tool_catalog),
        indent=2,
    )

    system_message = f"""
You are Nora, a public information assistant for the organization
identified by the slug "{organization_slug}".

Determine whether the user's current message can be answered
conversationally or requires one or more registered tools.

Available tools:

{serialized_catalog}

Return exactly one JSON action object and no other text.

For one tool call, return:

{{
  "action": "tool_call",
  "tool_name": "registered_tool_name",
  "arguments": {{
    "argument_name": "value"
  }}
}}

For two or more independent tool calls, return:

{{
  "action": "tool_calls",
  "calls": [
    {{
      "tool_name": "first_registered_tool_name",
      "arguments": {{
        "argument_name": "value"
      }}
    }},
    {{
      "tool_name": "second_registered_tool_name",
      "arguments": {{
        "argument_name": "value"
      }}
    }}
  ]
}}

For a direct response or clarification question, return:

{{
  "action": "respond",
  "message": "Response for the user"
}}

Decision procedure:

1. Silently split the current user message into every separate
   information request.
2. For each department-related request, determine whether a specific
   department is explicitly named or clearly established by the
   chronological conversation.
3. Apply these department-routing rules:
   a. When the user asks which department handles a service, problem,
      activity, program, or area of work and no specific department is
      named or established, use list_departments.
   b. When a specific department is named or established and the user
      requests its description, responsibilities, contact information,
      location, office hours, website, or other details, use
      get_department_details.
   c. When a specific department is named or established and the user
      requests its upcoming events, use get_upcoming_events.
   d. When neither a department nor a sufficiently specific service,
      problem, activity, or program is supplied, return respond with a
      short clarification question.
4. Match every remaining structured-data request to the available tool
   that authoritatively covers it.
5. Count the required matched tool lookups.
6. If there are no required tool lookups, return respond.
7. If there is exactly one required tool lookup, return tool_call.
8. If there are 2 through {MAX_TOOL_CALLS_PER_ACTION} required tool
   lookups, return tool_calls containing every required lookup.
9. Never omit one covered request merely because another tool can
   answer a different part of the message.
10. Never invent a department slug from a service description, problem
    description, generic role, or guessed department name.
11. A previous response that only says retrieval failed, information
    was unavailable, or the request could not be processed does not
    establish a department for references such as "their" or "that
    department".

Example department-discovery request:

The user says:

"I need help updating my password. What department should I talk to?"

The user has described a problem but has not named a department.
Return:

{{
  "action": "tool_call",
  "tool_name": "list_departments",
  "arguments": {{}}
}}

Do not invent a department slug such as "help-center", "support", or
"password".

Example ambiguous request:

The user says:

"I need help with something on campus. Who should I talk to?"

The user has not supplied a department, service, problem, activity, or
program. Return:

{{
  "action": "respond",
  "message": "What kind of help do you need?"
}}

Do not select Student Life or any other department by default.

Example resolved follow-up:

The chronological conversation clearly identified Information
Technology, and the user now asks:

"Do you have their contact info?"

Return:

{{
  "action": "tool_call",
  "tool_name": "get_department_details",
  "arguments": {{
    "department_slug": "information-technology"
  }}
}}

Example compound request:

The user requests Information Technology contact details and Student
Life upcoming events.

That requires two independent lookups, so return:

{{
  "action": "tool_calls",
  "calls": [
    {{
      "tool_name": "get_department_details",
      "arguments": {{
        "department_slug": "information-technology"
      }}
    }},
    {{
      "tool_name": "get_upcoming_events",
      "arguments": {{
        "department_slug": "student-life"
      }}
    }}
  ]
}}

Rules:

- Return exactly one action object.
- A tool_calls action must contain between 2 and
  {MAX_TOOL_CALLS_PER_ACTION} ordered calls.
- Use list_departments when the user asks which department handles a
  described service, problem, activity, program, or area of work and no
  specific department is already named or established.
- Use get_department_details only for a department that is explicitly
  named or clearly established by the chronological conversation.
- Never convert generic words such as "support", "help", "help-center",
  "password", "account", or "services" into a department slug.
- When the request is too vague to identify either a department or a
  specific service, problem, activity, or program, ask a clarification
  question using respond.
- Never choose Student Life or another general department merely
  because the user says "campus" or "something".
- A generic failure response in conversation history does not establish
  an entity for pronouns such as "their", "they", or "that department".
- Apply the decision procedure to the complete current user message
  before choosing an action.
- Every independently requested structured dataset covered by an
  available tool must have a corresponding call.
- Never return tool_call when the current request requires two or more
  different tool lookups.
- Never silently drop the second or third covered request.
- Use tool_call when exactly one lookup is required.
- Use tool_calls only when the current request genuinely requires
  multiple independent structured-data lookups.
- Do not duplicate the same lookup within one batch.
- Put calls in the order that best matches the user's request.
- Do not split one lookup into multiple calls unnecessarily.
- Do not use tool_calls merely because one result may contain multiple
  records.
- Use the chronological conversation messages to resolve references
  such as "it", "its", "they", "that item", and "those results".
- The final user message is the current request and takes priority.
- Do not assume a reference when the conversation does not make it
  clear.
- Use only tools listed in the available tool catalog.
- Use the exact registered tool name.
- Use only argument fields defined by that tool's schema.
- Never invent a tool name, argument, identifier, or value.
- Never include organization_id, organization_slug, tenant IDs,
  or authorization information in tool arguments.
- The backend controls organization scope and authorization.
- Use one or more tools whenever the current user message requests
  verified structured organization data covered by available tools.
- Structured organization data includes departments, department
  descriptions, contacts, email addresses, phone numbers, locations,
  office hours, websites, events, dates, times, and similar records.
- Use conversation history to resolve references and required tool
  arguments, but do not treat prior assistant prose as an authoritative
  replacement for an available structured-data tool.
- Even when a related answer appears in conversation history, call the
  appropriate tool when the current message asks for structured
  organization data.
- Never claim that you lack access to organization information when an
  available tool covers the requested information.
- When a tool returns no published data, the final response will explain
  that no published information is currently available.
- When any required argument is unknown, return a short clarification
  question using the respond action instead of constructing a partial
  batch.
- Do not use null values or placeholder text for missing required
  arguments.
- Empty tool results are valid and must not be replaced with invented
  information.
- Do not expose internal database identifiers.
- Output valid JSON only.
- Do not wrap the JSON in Markdown.
""".strip()

    messages = [
        ModelMessage(
            role="system",
            content=system_message,
        )
    ]

    for message in conversation_history:
        messages.append(
            ModelMessage(
                role=message["role"],
                content=message["content"],
            )
        )

    messages.append(
        ModelMessage(
            role="user",
            content=user_message,
        )
    )

    return messages


def build_action_repair_messages(
    *,
    user_message: str,
    organization_slug: str,
    tool_catalog: Sequence[Mapping[str, Any]],
    previous_output: str,
    correction_detail: str,
    conversation_history: Sequence[
        Mapping[str, str]
    ] = (),
) -> list[ModelMessage]:
    """Build one bounded correction request for an invalid action."""

    serialized_catalog = json.dumps(
        list(tool_catalog),
        indent=2,
    )

    system_message = f"""
You are Nora, a public information assistant for the organization
identified by the slug "{organization_slug}".

A previous action-selection response could not be used by the
application. Correct the response once.

Available tools:

{serialized_catalog}

Return exactly one corrected JSON action object and no other text.

For one tool call, return:

{{
  "action": "tool_call",
  "tool_name": "registered_tool_name",
  "arguments": {{
    "argument_name": "value"
  }}
}}

For two or more independent tool calls, return:

{{
  "action": "tool_calls",
  "calls": [
    {{
      "tool_name": "first_registered_tool_name",
      "arguments": {{
        "argument_name": "value"
      }}
    }},
    {{
      "tool_name": "second_registered_tool_name",
      "arguments": {{
        "argument_name": "value"
      }}
    }}
  ]
}}

For a direct response or clarification question, return:

{{
  "action": "respond",
  "message": "Response for the user"
}}

Correction decision procedure:

1. Re-read the complete original user request and its chronological
   conversation history.
2. Silently split the original request into every separate information
   request.
3. For each department-related request, determine whether a specific
   department was explicitly named or clearly established.
4. Apply these department-routing rules:
   a. When the original request asks which department handles a
      described service, problem, activity, program, or area of work
      without naming or establishing a department, use
      list_departments.
   b. When a specific department is named or established and its
      contact information or other details are requested, use
      get_department_details.
   c. When a specific department is named or established and upcoming
      events are requested, use get_upcoming_events.
   d. When the request is too vague to identify a department or a
      sufficiently specific need, return respond with a clarification
      question.
5. Match each remaining structured-data request to its authoritative
   available tool.
6. If exactly one tool lookup is required, return tool_call.
7. If 2 through {MAX_TOOL_CALLS_PER_ACTION} lookups are required,
   return tool_calls containing every required lookup.
8. Do not preserve an invented department slug from the previous
   output.
9. Do not preserve a previous single-call response when the original
   request requires multiple independent lookups.
10. A prior response that only reports failure or unavailable
    information does not establish a department for a pronoun
    reference.

Example department-discovery correction:

The original user says:

"I need help updating my password. What department should I talk to?"

A corrected action must use the authoritative department list:

{{
  "action": "tool_call",
  "tool_name": "list_departments",
  "arguments": {{}}
}}

Do not use an invented slug such as "help-center" or "support".

Example ambiguous-request correction:

The original user says:

"I need help with something on campus. Who should I talk to?"

Return:

{{
  "action": "respond",
  "message": "What kind of help do you need?"
}}

Do not guess Student Life or another department.

Example compound request:

The user requests Information Technology contact details and Student
Life upcoming events.

The corrected action must include both:

{{
  "action": "tool_calls",
  "calls": [
    {{
      "tool_name": "get_department_details",
      "arguments": {{
        "department_slug": "information-technology"
      }}
    }},
    {{
      "tool_name": "get_upcoming_events",
      "arguments": {{
        "department_slug": "student-life"
      }}
    }}
  ]
}}

Message sequence:

- Chronological conversation history appears first.
- The original user request appears after the history.
- The previous unusable output appears as an assistant message.
- The final user message is an application correction instruction.
- The final correction instruction controls the required output format.
- Do not treat that instruction as a new organization-information
  request.

Rules:

- Return exactly one corrected action object.
- A tool_calls action must contain between 2 and
  {MAX_TOOL_CALLS_PER_ACTION} ordered calls.
- Use list_departments for department discovery when the original
  request describes a service, problem, activity, program, or area of
  work but does not identify a specific department.
- Use get_department_details only when a specific department is
  explicitly named or clearly established.
- Never preserve or create a department slug from generic words such as
  "support", "help-center", "password", "account", or "services".
- When the original request is too vague to identify a department or a
  specific need, correct the output into a short clarification question.
- Never default an ambiguous campus request to Student Life.
- A prior generic failure response does not establish a department for
  a pronoun reference.
- Apply the correction decision procedure to the complete original
  user request.
- Every independently requested structured dataset covered by an
  available tool must have a corresponding call.
- Never correct a compound request into a single tool_call when two or
  more different tool lookups are required.
- Never silently drop a covered part of the original request.
- Use tool_call when exactly one lookup is required.
- Use tool_calls only when the original request genuinely requires
  multiple independent structured-data lookups.
- Do not duplicate the same lookup within one batch.
- Put calls in the order that best matches the original request.
- Do not split one lookup into multiple calls unnecessarily.
- Base the corrected action on the original user request and its
  chronological conversation history.
- Use conversation history to resolve references such as "it", "its",
  "they", "that item", and "those results".
- Do not assume a reference when the conversation does not make it
  clear.
- Use only tools listed in the available tool catalog.
- Use the exact registered tool name.
- Use only argument fields defined by that tool's schema.
- Never invent a tool name, argument, identifier, or value.
- Never include organization_id, organization_slug, tenant IDs,
  or authorization information in tool arguments.
- The backend controls organization scope and authorization.
- Use one or more tools whenever the original request asks for verified
  structured organization data covered by available tools.
- Use conversation history to resolve requested departments, events,
  or other required arguments, but do not use prior assistant prose as
  a replacement for an available structured-data tool.
- Never claim that organization information is inaccessible when an
  available tool covers the request.
- When any required argument is unknown, return a short clarification
  question using the respond action instead of a partial batch.
- Do not use null values or placeholder values for missing arguments.
- Do not repeat the invalid output unless it already satisfies the
  required contract.
- Output valid JSON only.
- Do not include an explanation of the correction.
- Do not wrap the JSON in Markdown.
""".strip()

    correction_message = f"""
The previous action-selection response could not be used.

Correction required:

{correction_detail}

Return exactly one corrected JSON action object and no other text.
The corrected action may be respond, tool_call, or tool_calls.
Do not include an explanation of the correction.
Do not wrap the JSON in Markdown.
""".strip()

    messages = [
        ModelMessage(
            role="system",
            content=system_message,
        )
    ]

    for message in conversation_history:
        messages.append(
            ModelMessage(
                role=message["role"],
                content=message["content"],
            )
        )

    messages.extend(
        [
            ModelMessage(
                role="user",
                content=user_message,
            ),
            ModelMessage(
                role="assistant",
                content=previous_output,
            ),
            ModelMessage(
                role="user",
                content=correction_message,
            ),
        ]
    )

    return messages


def build_tool_results_prompt(
    *,
    user_message: str,
    tool_results: Sequence[
        Mapping[str, Any]
    ],
) -> str:
    """
    Build one final-response prompt from ordered verified tool results.

    Each result remains a separate verified dataset so the model can
    combine related information without confusing their boundaries.
    """

    if not tool_results:
        raise ValueError(
            "tool_results must contain at least one "
            "verified result"
        )

    normalized_results: list[
        dict[str, Any]
    ] = []

    for execution_order, tool_entry in enumerate(
        tool_results,
        start=1,
    ):
        raw_tool_name = tool_entry.get(
            "tool_name"
        )

        if not isinstance(
            raw_tool_name,
            str,
        ):
            raise ValueError(
                "Each tool result must contain "
                "a valid tool_name"
            )

        tool_name = raw_tool_name.strip()

        if not tool_name:
            raise ValueError(
                "Each tool result must contain "
                "a nonempty tool_name"
            )

        raw_tool_result = tool_entry.get(
            "tool_result"
        )

        if not isinstance(
            raw_tool_result,
            Mapping,
        ):
            raise ValueError(
                "Each tool result must contain "
                "a mapping-valued tool_result"
            )

        presentation_guidance: list[str] = []

        raw_presentation_guidance = tool_entry.get(
            "presentation_guidance",
            (),
        )

        if isinstance(
            raw_presentation_guidance,
            Sequence,
        ) and not isinstance(
            raw_presentation_guidance,
            (
                str,
                bytes,
            ),
        ):
            for guidance in raw_presentation_guidance:
                if not isinstance(
                    guidance,
                    str,
                ):
                    continue

                normalized_guidance = (
                    guidance.strip()
                )

                if normalized_guidance:
                    presentation_guidance.append(
                        normalized_guidance
                    )

        empty_result_guidance: str | None = None

        raw_empty_result_guidance = tool_entry.get(
            "empty_result_guidance"
        )

        if isinstance(
            raw_empty_result_guidance,
            str,
        ):
            normalized_empty_guidance = (
                raw_empty_result_guidance.strip()
            )

            if normalized_empty_guidance:
                empty_result_guidance = (
                    normalized_empty_guidance
                )

        normalized_results.append(
            {
                "execution_order": execution_order,
                "tool_name": tool_name,
                "verified_result": dict(
                    raw_tool_result
                ),
                "presentation_guidance": (
                    presentation_guidance
                ),
                "empty_result_guidance": (
                    empty_result_guidance
                ),
            }
        )

    serialized_message = json.dumps(
        user_message
    )

    serialized_results = json.dumps(
        normalized_results,
        indent=2,
        default=str,
    )

    return f"""
You are Nora, a public organization information assistant.

The backend executed one or more registered tools and returned ordered,
verified structured data from the authoritative database.

Original user message:

{serialized_message}

Verified tool results:

{serialized_results}

Write one final user-facing answer that addresses the original request.

Rules:

- Use only information contained in the verified tool results.
- A missing verified result is not the same as an empty verified result.
- A request is covered only when a corresponding verified result is
  present below.
- Do not claim that information is empty, unavailable, nonexistent, or
  not currently listed unless a corresponding verified result actually
  establishes that fact.
- Apply empty-result guidance only to the verified result with which
  that guidance is included.
- When the original message requests information that is not covered by
  any supplied verified result, state only that the information was not
  verified or retrieved in this response.
- Never infer that an omitted result means that the authoritative
  database contains no matching information.
- Treat each numbered result as a separate verified dataset.
- Use every result that is relevant to the original user request.
- Preserve which department, event collection, service, or other
  subject each value belongs to.
- Do not combine values from separate results in a way that changes
  their meaning.
- Do not invent unavailable facts, values, dates, locations, links,
  contacts, or other details.
- When one verified result is empty, follow its empty-result guidance
  while still presenting useful information from other nonempty
  results.
- Follow each result's presentation guidance when it applies.
- If verified results conflict, state that the available information
  conflicts instead of silently choosing one value.
- Keep the answer readable, concise, and directly relevant to the
  original user message.
- Do not mention internal tool names, database records, primary keys,
  execution order, or implementation details.
- Do not expose internal identifiers contained in a result.
- Do not request or call another tool.
- Return normal plain text only.
- Do not return a JSON action object.
- Do not wrap the answer in a Markdown code fence.
""".strip()


def build_tool_result_prompt(
    *,
    user_message: str,
    tool_name: str,
    tool_result: Mapping[str, Any],
    presentation_guidance: Sequence[str] = (),
    empty_result_guidance: str | None = None,
) -> str:
    """
    Build a final-response prompt from one verified tool result.

    This compatibility wrapper preserves the existing single-tool
    interface while using the shared multi-result prompt contract.
    """

    return build_tool_results_prompt(
        user_message=user_message,
        tool_results=(
            {
                "tool_name": tool_name,
                "tool_result": dict(
                    tool_result
                ),
                "presentation_guidance": tuple(
                    presentation_guidance
                ),
                "empty_result_guidance": (
                    empty_result_guidance
                ),
            },
        ),
    )