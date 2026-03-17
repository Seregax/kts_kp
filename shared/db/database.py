from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(self) -> None:
        self._engine = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self, url: str) -> None:
        self._engine = create_async_engine(url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    async def disconnect(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def session(self) -> AsyncSession:
        assert self._session_factory is not None, "Database is not connected"
        return self._session_factory()
