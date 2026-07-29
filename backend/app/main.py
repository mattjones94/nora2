import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Response, status

from app.api.v1.router import router as api_v1_router
from app.conversation.session_maintenance_worker import (
    run_session_expiration_sweep_loop,
)
from app.core.config import get_settings
from app.database.engine import check_database, engine
from app.llm.client_factory import build_model_client
from app.llm.profile_registry import get_default_model_profile
from app.llm.runtime_provider import configure_model_runtime
from app.vector_store.qdrant import check_qdrant


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage resources owned by the API process."""

    settings = get_settings()

    model_profile = get_default_model_profile()

    model_client = build_model_client(
        profile=model_profile
    )

    configure_model_runtime(
        client=model_client,
        profile=model_profile,
    )

    expiration_sweep_task = asyncio.create_task(
        run_session_expiration_sweep_loop(
            interval_seconds=(
                settings
                .conversation_expiration_sweep_interval_seconds
            ),
            batch_size=(
                settings
                .conversation_expiration_sweep_batch_size
            ),
        ),
        name="conversation-session-expiration-sweep",
    )

    try:
        yield
    finally:
        expiration_sweep_task.cancel()

        with suppress(
            asyncio.CancelledError
        ):
            await expiration_sweep_task

        await engine.dispose()


app = FastAPI(
    title="NORA Server API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_v1_router)


@app.get("/api/v1/health/live")
async def health_live() -> dict[str, str]:
    """Confirm that the NORA API process is running."""

    return {
        "status": "alive",
        "service": "nora-api",
        "version": "0.1.0",
    }


@app.get("/api/v1/health/ready")
async def health_ready(
    response: Response,
) -> dict[str, object]:
    """Confirm that the API can reach its required services."""

    services = {
        "mysql": "unavailable",
        "qdrant": "unavailable",
    }

    try:
        await check_database()
        services["mysql"] = "available"
    except Exception:
        pass

    try:
        await check_qdrant()
        services["qdrant"] = "available"
    except Exception:
        pass

    is_ready = all(
        service_status == "available"
        for service_status in services.values()
    )

    if not is_ready:
        response.status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return {
        "status": (
            "ready"
            if is_ready
            else "not_ready"
        ),
        "services": services,
    }