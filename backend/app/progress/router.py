from fastapi import APIRouter

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.progress.schemas import ProgressReviewOut
from app.progress.service import build_review
from app.review import service as review_service
from app.review.router import TimezoneDep

router = APIRouter(tags=["progress"])


@router.get("/progress/review")
async def progress_review(
    user: CurrentUserDep, session: SessionDep, tz: TimezoneDep
) -> ProgressReviewOut:
    """How the learner is doing: this week against last, what went well, what is under way and
    what is next. Written by plain rules from their own records: no AI."""
    return await build_review(session, user.id, tz, review_service.utcnow())
