from fastapi import APIRouter

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.dashboard.schemas import DashboardOut
from app.dashboard.service import build_dashboard
from app.review import service as review_service
from app.review.router import TimezoneDep

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(user: CurrentUserDep, session: SessionDep, tz: TimezoneDep) -> DashboardOut:
    """Everything the home screen shows: am I on track, what should I do today, where am I
    weak, and the numbers behind them. Worked out now from the learner's own records."""
    return await build_dashboard(session, user.id, tz, review_service.utcnow())
