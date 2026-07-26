from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.session_repository import (
    ConversationSessionRepository,
)
from app.database.models.conversation_session import (
    ConversationSession,
)
from app.database.models.conversation_session_metric import (
    ConversationSessionMetric,
)


DEFAULT_SESSION_TIMEOUT_MINUTES = 15


class ConversationSessionError(Exception):
    """Base error raised while managing a conversation session."""


class InvalidConversationSessionIdError(
    ConversationSessionError
):
    """Raised when a supplied public session ID is not a valid UUID."""

    def __init__(self) -> None:
        super().__init__(
            "The supplied conversation session ID is invalid."
        )


class ConversationSessionNotFoundError(
    ConversationSessionError
):
    """Raised when a public session ID cannot be resolved."""

    def __init__(self) -> None:
        super().__init__(
            "The conversation session could not be found."
        )


class ConversationSessionUnavailableError(
    ConversationSessionError
):
    """Raised when a conversation session is no longer active."""

    def __init__(
        self,
        status: str,
    ) -> None:
        super().__init__(
            "The conversation session is no longer available. "
            f"Its current status is '{status}'."
        )


class ConversationSessionExpiredError(
    ConversationSessionUnavailableError
):
    """Raised when a session has passed its inactivity deadline."""

    def __init__(self) -> None:
        super().__init__(
            status="expired",
        )


class ConversationSessionService:
    """Manage public conversation-session lifecycle rules."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        timeout_minutes: int = DEFAULT_SESSION_TIMEOUT_MINUTES,
    ) -> None:
        if timeout_minutes < 1:
            raise ValueError(
                "timeout_minutes must be at least 1"
            )

        self._session = session
        self._sessions = ConversationSessionRepository(
            session
        )
        self._timeout = timedelta(
            minutes=timeout_minutes
        )

    async def resolve_or_create(
        self,
        *,
        organization_id: int,
        public_id: str | None,
        model_profile_key: str,
        channel: str = "web",
    ) -> ConversationSession:
        """
        Create a session when no public ID is supplied, otherwise resolve
        and renew the existing active session.
        """

        if public_id is None:
            return await self.create(
                organization_id=organization_id,
                model_profile_key=model_profile_key,
                channel=channel,
            )

        return await self.get_active(
            organization_id=organization_id,
            public_id=public_id,
        )

    async def create(
        self,
        *,
        organization_id: int,
        model_profile_key: str,
        channel: str = "web",
    ) -> ConversationSession:
        """Create a new active public conversation session."""

        if organization_id < 1:
            raise ValueError(
                "organization_id must be a positive integer"
            )

        normalized_profile_key = (
            model_profile_key.strip()
        )

        if not normalized_profile_key:
            raise ValueError(
                "model_profile_key cannot be empty"
            )

        normalized_channel = channel.strip().lower()

        if not normalized_channel:
            raise ValueError(
                "channel cannot be empty"
            )

        if len(normalized_channel) > 50:
            raise ValueError(
                "channel cannot exceed 50 characters"
            )

        now = self._utc_now()

        conversation_session = ConversationSession(
            public_id=str(uuid4()),
            organization_id=organization_id,
            status="active",
            channel=normalized_channel,
            model_profile_key=normalized_profile_key,
            started_at=now,
            last_activity_at=now,
            expires_at=now + self._timeout,
        )

        conversation_session.metrics = (
            ConversationSessionMetric(
                organization_id=organization_id,
                completion_status="in_progress",
            )
        )

        try:
            await self._sessions.create(
                conversation_session
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return conversation_session

    async def get_active(
        self,
        *,
        organization_id: int,
        public_id: str,
    ) -> ConversationSession:
        """
        Resolve an active session and renew its inactivity deadline.
        """

        normalized_public_id = self._normalize_public_id(
            public_id
        )

        conversation_session = (
            await self._sessions.get_by_public_id(
                organization_id=organization_id,
                public_id=normalized_public_id,
            )
        )

        if conversation_session is None:
            raise ConversationSessionNotFoundError()

        if conversation_session.status != "active":
            raise ConversationSessionUnavailableError(
                status=conversation_session.status,
            )

        now = self._utc_now()

        if conversation_session.expires_at <= now:
            try:
                await self._sessions.update(
                    conversation_session=conversation_session,
                    changes={
                        "status": "expired",
                        "ended_at": now,
                        "close_reason": "inactivity_timeout",
                    },
                )

                await self._session.commit()

            except Exception:
                await self._session.rollback()
                raise

            raise ConversationSessionExpiredError()

        try:
            renewed_session = await self._sessions.update(
                conversation_session=conversation_session,
                changes={
                    "last_activity_at": now,
                    "expires_at": now + self._timeout,
                },
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return renewed_session

    def _normalize_public_id(
        self,
        public_id: str,
    ) -> str:
        """Validate and normalize a public UUID."""

        try:
            parsed_id = UUID(
                public_id.strip()
            )
        except (
            AttributeError,
            ValueError,
        ) as error:
            raise InvalidConversationSessionIdError() from error

        return str(parsed_id)

    def _utc_now(self) -> datetime:
        """
        Return naive UTC because the current MySQL DateTime columns do not
        store timezone information.
        """

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )