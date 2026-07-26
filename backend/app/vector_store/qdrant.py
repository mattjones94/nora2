import httpx

from app.core.config import get_settings


settings = get_settings()


async def check_qdrant() -> None:
    """Confirm that the Qdrant HTTP service is reachable."""

    async with httpx.AsyncClient(
        base_url=settings.qdrant_url,
        timeout=3.0,
    ) as client:
        response = await client.get("/")
        response.raise_for_status()

        data = response.json()

        if data.get("title") != "qdrant - vector search engine":
            raise RuntimeError("Unexpected response from Qdrant")