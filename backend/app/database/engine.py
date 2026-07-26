from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import get_settings


def build_database_url() -> URL:
    """Build the MySQL URL from environment-based settings."""

    settings = get_settings()

    return URL.create(
        drivername="mysql+asyncmy",
        username=settings.mysql_user,
        password=settings.mysql_password,
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
    )


engine: AsyncEngine = create_async_engine(
    build_database_url(),
    pool_pre_ping=True,
)


async def check_database() -> None:
    """Run a small query to confirm that MySQL is reachable."""

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))