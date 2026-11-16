from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserDep
from app.core.database import get_session

router = APIRouter()


class HealthOut(BaseModel):
    status: Literal["ok"]


class MeOut(BaseModel):
    id: str
    email: str | None


@router.get("/health", tags=["system"])
async def health() -> HealthOut:
    """Liveness check used by Render and by the app to wake the server."""
    return HealthOut(status="ok")


@router.get("/health/db", tags=["system"])
async def health_db(session: Annotated[AsyncSession, Depends(get_session)]) -> HealthOut:
    """Checks that the database is reachable."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc
    return HealthOut(status="ok")


@router.get("/me", tags=["auth"])
async def me(user: CurrentUserDep) -> MeOut:
    """Returns the logged-in user. Proves the login token is accepted end to end."""
    return MeOut(id=str(user.id), email=user.email)
