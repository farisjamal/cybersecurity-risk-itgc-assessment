"""Async SQLAlchemy setup."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from bank_lab.config import Settings


class Base(DeclarativeBase):
    """Declarative model base."""


def build_engine(settings: Settings) -> AsyncEngine:
    if settings.database_url.startswith("sqlite+aiosqlite:///"):
        raw_path = settings.database_url.removeprefix("sqlite+aiosqlite:///")
        if raw_path and raw_path != ":memory:":
            Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(settings.database_url, pool_pre_ping=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
