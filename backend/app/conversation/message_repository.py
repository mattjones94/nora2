from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation_message import (
    ConversationMessage,
)


class ConversationMessageRepository:
    """Handle persistence operations for conversation messages."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create(
        self,
        message: ConversationMessage,
    ) -> ConversationMessage:
        """Add one conversation message to the transaction."""

        self._session.add(message)

        await self._session.flush()
        await self._session.refresh(message)

        return message

    async def get_next_sequence_number(
        self,
        session_id: int,
    ) -> int:
        """Return the next ordered message number for a session."""

        statement = select(
            func.coalesce(
                func.max(
                    ConversationMessage.sequence_number
                ),
                0,
            )
            + 1
        ).where(
            ConversationMessage.session_id == session_id,
        )

        sequence_number = await self._session.scalar(
            statement
        )

        return int(
            sequence_number or 1
        )

    async def list_recent_visible(
        self,
        session_id: int,
        *,
        limit: int = 20,
    ) -> list[ConversationMessage]:
        """Return recent completed public messages in chronological order."""

        statement = (
            select(
                ConversationMessage
            )
            .where(
                ConversationMessage.session_id == session_id,
                ConversationMessage.is_user_visible.is_(True),
                ConversationMessage.status == "completed",
                ConversationMessage.message_type.in_(
                    (
                        "user_message",
                        "assistant_message",
                    )
                ),
            )
            .order_by(
                ConversationMessage.sequence_number.desc()
            )
            .limit(limit)
        )

        result = await self._session.scalars(
            statement
        )

        messages = list(
            result.all()
        )

        messages.reverse()

        return messages