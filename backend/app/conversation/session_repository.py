from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation_session import (
    ConversationSession,
)


class ConversationSessionRepository:
    """Handle persistence operations for conversation sessions."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create(
        self,
        conversation_session: ConversationSession,
    ) -> ConversationSession:
        """Add a conversation session to the current transaction."""

        self._session.add(
            conversation_session
        )

        await self._session.flush()
        await self._session.refresh(
            conversation_session
        )

        return conversation_session

    async def get_by_public_id(
        self,
        organization_id: int,
        public_id: str,
    ) -> ConversationSession | None:
        """Find an organization-scoped session by its public UUID."""

        statement = select(
            ConversationSession
        ).where(
            ConversationSession.organization_id == organization_id,
            ConversationSession.public_id == public_id,
        )

        result = await self._session.scalars(
            statement
        )

        return result.one_or_none()

    async def update(
        self,
        conversation_session: ConversationSession,
        changes: Mapping[str, object],
    ) -> ConversationSession:
        """Apply lifecycle changes to a conversation session."""

        for field_name, value in changes.items():
            setattr(
                conversation_session,
                field_name,
                value,
            )

        await self._session.flush()
        await self._session.refresh(
            conversation_session
        )

        return conversation_session