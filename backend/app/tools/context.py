from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Trusted organization scope supplied to LLM tools by the backend."""

    organization_id: int
    organization_slug: str

    def __post_init__(self) -> None:
        if self.organization_id < 1:
            raise ValueError(
                "organization_id must be a positive integer"
            )

        if not self.organization_slug.strip():
            raise ValueError(
                "organization_slug cannot be empty"
            )