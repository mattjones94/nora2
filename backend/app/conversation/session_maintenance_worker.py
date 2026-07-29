import asyncio
import logging

from app.conversation.session_maintenance import (
    ConversationSessionMaintenanceService,
)
from app.database.session import AsyncSessionLocal


logger = logging.getLogger(__name__)


async def run_session_expiration_sweep_loop(
    *,
    interval_seconds: int,
    batch_size: int,
) -> None:
    """
    Periodically expire inactive conversation sessions.

    Each sweep receives an independent database session. Cancellation
    propagates normally so the FastAPI lifespan can stop the worker
    cleanly during application shutdown.
    """

    if interval_seconds < 1:
        raise ValueError(
            "interval_seconds must be at least 1"
        )

    if batch_size < 1:
        raise ValueError(
            "batch_size must be at least 1"
        )

    if batch_size > 1000:
        raise ValueError(
            "batch_size cannot exceed 1000"
        )

    while True:
        await asyncio.sleep(
            interval_seconds
        )

        try:
            async with AsyncSessionLocal() as session:
                maintenance_service = (
                    ConversationSessionMaintenanceService(
                        session
                    )
                )

                expired_count = (
                    await maintenance_service
                    .expire_inactive_sessions(
                        limit=batch_size,
                    )
                )

            if expired_count > 0:
                logger.info(
                    "Expired %s inactive conversation session(s).",
                    expired_count,
                )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Conversation session expiration sweep failed."
            )