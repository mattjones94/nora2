from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRequest(BaseModel):
    """A public user message submitted to NORA."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    message: str = Field(
        min_length=1,
        max_length=4000,
    )

    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class ChatMessageResponse(BaseModel):
    """A completed public chat response."""

    organization_id: int
    organization_slug: str
    session_id: str
    assistant_message: str