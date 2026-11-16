from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.ai import budget
from app.ai.deps import LimitsDep, ProvidersDep
from app.ai.errors import AiError, AiLimitError
from app.ai.gateway import utcnow
from app.ai.prompts import TEMPLATES, Feature
from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.core.types import UtcDatetime

router = APIRouter(prefix="/ai", tags=["ai"])


class FeatureQuotaOut(BaseModel):
    feature: Feature
    label: str  # for "8 sentence checks left today"
    limit: int
    used: int
    remaining: int


class QuotaOut(BaseModel):
    # False when no provider is set up or every provider has hit its shared daily ceiling.
    available: bool
    resets_at: UtcDatetime
    features: list[FeatureQuotaOut]


class AiErrorOut(BaseModel):
    code: str
    message: str
    retry_after_seconds: int | None = None
    resets_at: datetime | None = None


@router.get("/quota")
async def quota(
    user: CurrentUserDep,
    session: SessionDep,
    providers: ProvidersDep,
    limits: LimitsDep,
) -> QuotaOut:
    """What the learner has left today, per feature. Cheap: no AI is called."""
    now = utcnow()
    day = budget.usage_day(now)
    usage = await budget.user_usage(session, user.id, day)

    available = False
    for provider in providers:
        ceiling = limits.provider.get(provider.name, budget.ProviderCeiling())
        if budget.provider_has_room(
            ceiling, await budget.provider_usage(session, provider.name, day)
        ):
            available = True
            break

    overall_left = 0
    if usage.tokens < limits.user_tokens:
        overall_left = max(0, limits.user_requests - usage.requests)
    features = []
    for feature, template in TEMPLATES.items():
        cap = limits.feature_requests[feature]
        used = usage.by_feature.get(feature.value, 0)
        features.append(
            FeatureQuotaOut(
                feature=feature,
                label=template.label,
                limit=cap,
                used=used,
                remaining=min(max(0, cap - used), overall_left),
            )
        )
    return QuotaOut(available=available, resets_at=budget.next_reset(now), features=features)


async def ai_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Turns AiErrors into clean JSON the app can show, instead of a 500."""
    assert isinstance(exc, AiError)
    body = AiErrorOut(
        code=exc.code,
        message=exc.message,
        retry_after_seconds=exc.retry_after_seconds,
        resets_at=exc.resets_at if isinstance(exc, AiLimitError) else None,
    )
    headers = {"Retry-After": str(exc.retry_after_seconds)} if exc.retry_after_seconds else None
    return JSONResponse(
        {"detail": body.model_dump(mode="json")}, status_code=exc.status_code, headers=headers
    )
