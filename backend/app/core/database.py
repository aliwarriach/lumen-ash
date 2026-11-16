from collections.abc import AsyncIterator
from datetime import datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends
from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

# Predictable constraint names, so migrations can drop or alter them later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all ORM models. Alembic reads its metadata."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class OwnedMixin:
    """Columns every learner-owned table has. Every query must filter by `user_id`."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # The Supabase auth user id. Not a foreign key: auth.users lives in Supabase's own schema.
    user_id: Mapped[UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    if settings.environment == "test":
        # Tests run each request in a fresh event loop; pooled connections can't cross loops.
        return create_async_engine(settings.database_url, poolclass=NullPool)
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,  # free hosts drop idle connections
        pool_size=5,
        max_overflow=0,  # stay well inside Supabase's free connection limit
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
