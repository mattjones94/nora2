from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.metrics_repository import (
    ConversationMetricsRepository,
)
from app.conversation.session_repository import (
    ConversationSessionRepository,
)


DEFAULT_EXPIRATION_BATCH_SIZE = 100
MAXIMUM_EXPIRATION_BATCH_SIZE = 1000


class ConversationSessionMaintenanceError(Exception):
    """Base error raised during conversation-session maintenance."""


class ConversationSessionMetricsMissingError(
    ConversationSessionMaintenanceError
):
    """Raised when an expiring session has no metrics record."""

    def __init__(
        self,
        session_id: int,
    ) -> None:
        super().__init__(
            "The conversation session metrics record could not be "
            f"found for session ID {session_id}."
        )


class ConversationSessionMaintenanceService:
    """Run database maintenance for conversation-session lifecycle."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

        self._sessions = ConversationSessionRepository(
            session
        )

        self._metrics = ConversationMetricsRepository(
            session
        )

    async def expire_inactive_sessions(
        self,
        *,
        limit: int = DEFAULT_EXPIRATION_BATCH_SIZE,
    ) -> int:
        """
        Expire one batch of active sessions past their inactivity deadline.

        The session and its metrics record are updated in one transaction.
        The returned integer is the number of sessions expired.
        """

        if limit < 1:
            raise ValueError(
                "limit must be at least 1"
            )

        if limit > MAXIMUM_EXPIRATION_BATCH_SIZE:
            raise ValueError(
                "limit cannot exceed "
                f"{MAXIMUM_EXPIRATION_BATCH_SIZE}"
            )

        now = self._utc_now()

        try:
            expired_sessions = (
                await self._sessions.list_expired_active(
                    expired_at_or_before=now,
                    limit=limit,
                )
            )

            for conversation_session in expired_sessions:
                metrics = await self._metrics.get_by_session_id(
                    session_id=conversation_session.id,
                )

                if metrics is None:
                    raise ConversationSessionMetricsMissingError(
                        session_id=conversation_session.id,
                    )

                await self._sessions.update(
                    conversation_session=conversation_session,
                    changes={
                        "status": "expired",
                        "ended_at": now,
                        "close_reason": "inactivity_timeout",
                    },
                )

                await self._metrics.update(
                    metrics=metrics,
                    changes={
                        "completion_status": "expired",
                    },
                )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return len(
            expired_sessions
        )

    def _utc_now(self) -> datetime:
        """Return naive UTC for the current MySQL DateTime fields."""

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )