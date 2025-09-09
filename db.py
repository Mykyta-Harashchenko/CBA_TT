import contextlib
import logging
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from conf.config import config


class DatabaseSessionManager:
    def __init__(self, url: str):
        self._engine: AsyncEngine = create_async_engine(url, echo=False)
        self._session_maker = sessionmaker(
            bind=self._engine, expire_on_commit=False, class_=AsyncSession
        )

    @contextlib.asynccontextmanager
    async def session(self):
        async with self._session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception as err:
                logging.error(f"DB session rollback because of {err}")
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        await self._engine.dispose()


sessionmanager = DatabaseSessionManager(config.DB_URL)


async def get_db():
    async with sessionmanager.session() as session:
        yield session