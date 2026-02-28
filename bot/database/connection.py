from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from bot.management.settings import get_settings

settings = get_settings()

engine = create_async_engine(
    url=settings.async_postgres_url,
    echo=False
)

sessionmaker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@asynccontextmanager
async def get_session() -> AsyncSession:
    async with sessionmaker() as session:
        yield session