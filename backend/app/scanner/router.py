from fastapi import APIRouter

from app.ai.deps import GatewayDep
from app.coach.deps import LanguageToolDep
from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.scanner import service
from app.scanner.schemas import ScanHelpIn, ScanHelpOut

router = APIRouter(prefix="/scanner", tags=["scanner"])


@router.post("/help")
async def help_with_exercise(
    body: ScanHelpIn,
    user: CurrentUserDep,
    session: SessionDep,
    gateway: GatewayDep,
    languagetool: LanguageToolDep,
) -> ScanHelpOut:
    """Hints and checked answers for a textbook exercise the phone read from a photo.

    Send the text the learner has reviewed; the photo never leaves the phone. Nothing is stored.
    Uses one 'exercise help' of the day's AI allowance (the same exercise asked again is free).
    The answers carry a Confirmed / Likely / Uncertain label; show the hint first and the answer
    only when asked. To practise, the learner writes their own sentence and sends it to
    `POST /coach/check`."""
    return await service.help_with_exercise(session, gateway, languagetool, user.id, body.text)
