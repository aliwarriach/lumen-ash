"""Daily budgets, shared ceilings and the burst throttle. All state lives in Postgres.

Checking and reserving happen together in one transaction, under a short advisory lock, so two
requests arriving at once can't both slip under a limit. The lock is held only while checking and
counting (a few queries), never while waiting for a provider.

Token limits can overshoot by one call: tokens are only known once the provider has answered, so
a call that starts just under the limit may end just over it. Every call is bounded by
`max_input_chars` and `max_output_tokens`, so the overshoot is small.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AiLimitError
from app.ai.models import AiUsage
from app.ai.prompts import TEMPLATES, Feature
from app.core.config import Settings

BURST_WINDOW = timedelta(seconds=60)
_LOCK_KEY = 0x4C554D454E  # "LUMEN": one lock for the AI reservation step


@dataclass(frozen=True)
class ProviderCeiling:
    requests: int | None = None
    tokens: int | None = None


@dataclass(frozen=True)
class Limits:
    user_requests: int
    user_tokens: int
    feature_requests: Mapping[Feature, int]
    burst_per_minute: int
    provider: Mapping[str, ProviderCeiling]

    @classmethod
    def from_settings(cls, settings: Settings) -> "Limits":
        caps = {feature: t.default_daily_cap for feature, t in TEMPLATES.items()}
        for name, cap in settings.ai_feature_daily_caps.items():
            try:
                caps[Feature(name)] = cap
            except ValueError as exc:  # a typo here would silently leave a feature uncapped
                raise ValueError(f"Unknown feature in AI_FEATURE_DAILY_CAPS: {name}") from exc
        return cls(
            user_requests=settings.ai_user_daily_requests,
            user_tokens=settings.ai_user_daily_tokens,
            feature_requests=caps,
            burst_per_minute=settings.ai_burst_per_minute,
            provider={
                "gemini": ProviderCeiling(
                    settings.gemini_daily_request_ceiling, settings.gemini_daily_token_ceiling
                ),
                # Each Groq key has its own allowance, so each is counted on its own.
                "groq": ProviderCeiling(
                    settings.groq_daily_request_ceiling, settings.groq_daily_token_ceiling
                ),
                "groq_backup": ProviderCeiling(
                    settings.groq_daily_request_ceiling, settings.groq_daily_token_ceiling
                ),
            },
        )


def usage_day(now: datetime) -> date:
    """Quotas run on UTC dates. A client-supplied timezone would let it reset its own limit."""
    return now.astimezone(UTC).date()


def next_reset(now: datetime) -> datetime:
    return datetime.combine(usage_day(now) + timedelta(days=1), time.min, tzinfo=UTC)


@dataclass(frozen=True)
class UserUsage:
    requests: int
    tokens: int
    by_feature: Mapping[str, int]


async def user_usage(session: AsyncSession, user_id: UUID, day: date) -> UserUsage:
    rows = (
        await session.execute(
            select(
                AiUsage.feature,
                func.sum(AiUsage.requests),
                func.sum(AiUsage.input_tokens + AiUsage.output_tokens),
            )
            .where(AiUsage.user_id == user_id, AiUsage.usage_date == day)
            .group_by(AiUsage.feature)
        )
    ).all()
    return UserUsage(
        requests=sum(int(r[1]) for r in rows),
        tokens=sum(int(r[2]) for r in rows),
        by_feature={r[0]: int(r[1]) for r in rows},
    )


@dataclass(frozen=True)
class ProviderUsage:
    requests: int
    tokens: int


async def provider_usage(session: AsyncSession, provider: str, day: date) -> ProviderUsage:
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(AiUsage.requests), 0),
                func.coalesce(func.sum(AiUsage.input_tokens + AiUsage.output_tokens), 0),
            ).where(AiUsage.provider == provider, AiUsage.usage_date == day)
        )
    ).one()
    return ProviderUsage(requests=int(row[0]), tokens=int(row[1]))


def provider_has_room(ceiling: ProviderCeiling, used: ProviderUsage) -> bool:
    if ceiling.requests is not None and used.requests >= ceiling.requests:
        return False
    return not (ceiling.tokens is not None and used.tokens >= ceiling.tokens)


async def check_burst(session: AsyncSession, user_id: UUID, now: datetime, limit: int) -> None:
    """Counts this request in the learner's one-minute window, or raises if the window is full.

    A single atomic upsert: it starts a new window if the old one has ended, otherwise adds one
    and refuses once the window holds `limit` requests.
    """
    cutoff = now - BURST_WINDOW
    result = await session.execute(
        text(
            """
            INSERT INTO ai_burst AS b (user_id, window_start, count)
            VALUES (:user_id, :now, 1)
            ON CONFLICT (user_id) DO UPDATE SET
                window_start = CASE WHEN b.window_start <= :cutoff
                    THEN :now ELSE b.window_start END,
                count = CASE WHEN b.window_start <= :cutoff THEN 1 ELSE b.count + 1 END
            WHERE b.window_start <= :cutoff OR b.count < :limit
            RETURNING count
            """
        ),
        {"user_id": user_id, "now": now, "cutoff": cutoff, "limit": limit},
    )
    if result.first() is not None:
        return
    window_start = await session.scalar(
        text("SELECT window_start FROM ai_burst WHERE user_id = :user_id"), {"user_id": user_id}
    )
    wait = (window_start + BURST_WINDOW - now).total_seconds() if window_start else 1
    seconds = max(1, int(wait) + 1)
    raise AiLimitError(
        "too_fast",
        f"Too many AI requests in a row. Try again in {seconds} seconds.",
        retry_after_seconds=seconds,
    )


async def lock_for_reservation(session: AsyncSession) -> None:
    """Serialises reservations until the transaction ends (commit or rollback)."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY})


async def reserve(
    session: AsyncSession,
    user_id: UUID,
    feature: Feature,
    provider: str,
    now: datetime,
    limits: Limits,
) -> bool:
    """Checks every limit and, if all pass, counts one request for this provider.

    Raises AiLimitError if the learner is over one of their own limits. Returns False if the
    provider itself has reached its shared ceiling (the caller then tries the next provider).
    The caller must commit straight after, which also releases the lock.
    """
    day = usage_day(now)
    await lock_for_reservation(session)

    usage = await user_usage(session, user_id, day)
    resets_at = next_reset(now)
    feature_cap = limits.feature_requests[feature]
    if usage.requests >= limits.user_requests or usage.tokens >= limits.user_tokens:
        raise AiLimitError(
            "daily_limit",
            "You've used all of today's AI help. It comes back tomorrow; the rest still works.",
            resets_at=resets_at,
        )
    if usage.by_feature.get(feature.value, 0) >= feature_cap:
        raise AiLimitError(
            "feature_limit",
            f"You've used all of today's {TEMPLATES[feature].label}. They come back tomorrow.",
            resets_at=resets_at,
        )

    ceiling = limits.provider.get(provider, ProviderCeiling())
    if not provider_has_room(ceiling, await provider_usage(session, provider, day)):
        return False

    await session.execute(
        insert(AiUsage)
        .values(
            user_id=user_id,
            usage_date=day,
            feature=feature.value,
            provider=provider,
            requests=1,
            input_tokens=0,
            output_tokens=0,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "usage_date", "feature", "provider"],
            set_={"requests": AiUsage.requests + 1, "updated_at": func.now()},
        )
    )
    return True


async def settle(
    session: AsyncSession,
    user_id: UUID,
    feature: Feature,
    provider: str,
    now: datetime,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    refund: bool = False,
) -> None:
    """Records the real token counts after the call, or gives the request back if it failed."""
    values: dict[str, object] = {
        "input_tokens": AiUsage.input_tokens + input_tokens,
        "output_tokens": AiUsage.output_tokens + output_tokens,
        "updated_at": func.now(),
    }
    if refund:
        values["requests"] = func.greatest(AiUsage.requests - 1, 0)
    await session.execute(
        update(AiUsage)
        .where(
            AiUsage.user_id == user_id,
            AiUsage.usage_date == usage_day(now),
            AiUsage.feature == feature.value,
            AiUsage.provider == provider,
        )
        .values(**values)
    )
