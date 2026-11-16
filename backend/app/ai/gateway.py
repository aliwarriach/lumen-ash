"""The one way the rest of the app calls AI.

    result = await gateway.run(user.id, SENTENCE_COACH, {"sentence": ..., ...})

Steps, in order, each one cheaper than the next:
1. Redact personal details and reject over-long input.
2. Look in the cache. A hit costs nothing and uses none of the learner's budget.
3. Burst throttle, then the learner's daily limits.
4. Try each provider in the configured order. A rate limit, quota error or outage moves on to the
   next provider and gives the request back to the learner. An answer that is cut off, not JSON or
   the wrong shape also moves on (the tokens it cost stay counted). Nothing left means
   "AI unavailable", or "unusable answer" if a provider did answer.
5. Check the answer against the template's schema, cache it and record the real token counts.
"""

import hashlib
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import budget
from app.ai.errors import (
    AiBadResponseError,
    AiInputError,
    AiUnavailableError,
    ProviderBadOutput,
    ProviderMisconfigured,
    ProviderRateLimited,
    ProviderUnavailable,
)
from app.ai.models import AiCache
from app.ai.prompts import PromptTemplate
from app.ai.providers import AiProvider
from app.ai.redact import normalize, redact

log = logging.getLogger(__name__)

UNAVAILABLE = "AI help isn't available right now. Everything else still works; try again later."
BAD_ANSWER = "The AI gave an unusable answer. Please try again."
SHARED_LIMIT = "The shared AI allowance for today is used up. Try again tomorrow."

# How long to leave a provider alone after it fails, so every request doesn't wait on it.
RATE_LIMIT_COOLDOWN = timedelta(seconds=60)
OUTAGE_COOLDOWN = timedelta(seconds=30)
# A rejected key, an account with no credit or a retired model stays broken until someone changes
# a setting. Asking again every 30 seconds would add a failed round trip to every request.
MISCONFIGURED_COOLDOWN = timedelta(minutes=10)

# An answer nobody has asked for in this long is deleted. Cached answers come from what the learner
# wrote or pasted, so they shouldn't be kept for ever, and the free database is small.
CACHE_TTL = timedelta(days=30)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Cooldowns:
    """Providers recently seen failing. Kept in memory: losing it on restart is harmless."""

    def __init__(self) -> None:
        self._until: dict[str, datetime] = {}

    def active(self, provider: str, now: datetime) -> bool:
        return self._until.get(provider, now) > now

    def start(self, provider: str, now: datetime, duration: timedelta) -> None:
        self._until[provider] = now + duration


@dataclass(frozen=True)
class AiResult:
    output: BaseModel
    cached: bool
    provider: str | None  # None when the answer came from the cache


class AiGateway:
    def __init__(
        self,
        session: AsyncSession,
        providers: Sequence[AiProvider],
        limits: budget.Limits,
        cooldowns: Cooldowns,
        redact_names: Sequence[str] = (),
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._session = session
        self._providers = providers
        self._limits = limits
        self._cooldowns = cooldowns
        self._redact_names = redact_names
        self._clock = clock

    async def run(
        self,
        user_id: UUID,
        template: PromptTemplate,
        fields: Mapping[str, str],
        extra_names: Sequence[str] = (),
    ) -> AiResult:
        names = [*self._redact_names, *extra_names]
        clean = {k: normalize(redact(v, names)) for k, v in fields.items()}
        if sum(len(v) for v in clean.values()) > template.max_input_chars:
            raise AiInputError("That text is too long to check. Try a shorter piece.")
        request = template.render(clean)

        key = hashlib.sha256(
            f"{template.feature.value}\n{template.version}\n{request.user}".encode()
        ).hexdigest()
        if (cached := await self._from_cache(key, template)) is not None:
            return AiResult(cached, cached=True, provider=None)

        await budget.check_burst(
            self._session, user_id, self._clock(), self._limits.burst_per_minute
        )
        await self._session.commit()

        skipped_for_ceiling = 0
        bad_answer: Exception | None = None
        for provider in self._providers:
            now = self._clock()
            if self._cooldowns.active(provider.name, now):
                continue
            if not await budget.reserve(
                self._session, user_id, template.feature, provider.name, now, self._limits
            ):
                await self._session.commit()
                skipped_for_ceiling += 1
                continue
            await self._session.commit()  # the reservation is now visible and the lock released

            give_back = _Settle(self._session, user_id, template, provider.name, now)

            try:
                response = await provider.generate(request)
            except ProviderRateLimited as exc:
                log.warning("%s rate limited; trying the next provider", provider.name)
                duration = (
                    timedelta(seconds=exc.retry_after_seconds)
                    if exc.retry_after_seconds
                    else RATE_LIMIT_COOLDOWN
                )
                self._cooldowns.start(provider.name, self._clock(), duration)
                await give_back.refund()
                continue
            except ProviderUnavailable as exc:
                log.warning("%s unavailable (%s); trying the next provider", provider.name, exc)
                duration = (
                    MISCONFIGURED_COOLDOWN
                    if isinstance(exc, ProviderMisconfigured)
                    else OUTAGE_COOLDOWN
                )
                self._cooldowns.start(provider.name, self._clock(), duration)
                await give_back.refund()
                continue
            except ProviderBadOutput as exc:
                # The provider spent tokens on it, so the request stays counted. Another provider
                # may well do better, so carry on down the list.
                log.warning("%s gave unusable output: %s", provider.name, exc)
                await give_back.tokens(exc.input_tokens, exc.output_tokens)
                bad_answer = exc
                continue

            try:
                output = template.output_model.model_validate(response.data)
            except ValidationError as exc:
                log.warning("%s output didn't match %s", provider.name, template.feature.value)
                await give_back.tokens(response.input_tokens, response.output_tokens)
                bad_answer = exc
                continue

            await self._store(key, template, output, response.provider, response.model)
            await give_back.tokens(response.input_tokens, response.output_tokens)
            return AiResult(output, cached=False, provider=response.provider)

        if bad_answer is not None:
            raise AiBadResponseError(BAD_ANSWER) from bad_answer
        if self._providers and skipped_for_ceiling == len(self._providers):
            raise AiUnavailableError(SHARED_LIMIT, code="shared_limit")
        raise AiUnavailableError(UNAVAILABLE)

    async def _from_cache(self, key: str, template: PromptTemplate) -> BaseModel | None:
        row = await self._session.get(AiCache, key)
        if row is None:
            return None
        try:
            output = template.output_model.model_validate(row.response)
        except ValidationError:  # the output model changed since this was stored
            await self._session.delete(row)
            await self._session.commit()
            return None
        await self._session.execute(
            update(AiCache)
            .where(AiCache.key == key)
            .values(hits=AiCache.hits + 1, last_hit_at=self._clock())
        )
        await self._session.commit()
        return output

    async def _store(
        self, key: str, template: PromptTemplate, output: BaseModel, provider: str, model: str
    ) -> None:
        await self._session.execute(
            insert(AiCache)
            .values(
                key=key,
                feature=template.feature.value,
                template_version=template.version,
                response=output.model_dump(mode="json"),
                provider=provider,
                model=model,
                hits=0,
            )
            .on_conflict_do_nothing(index_elements=["key"])
        )
        # No background job exists to tidy up, so each new answer clears out the stale ones.
        await self._session.execute(
            delete(AiCache).where(
                func.coalesce(AiCache.last_hit_at, AiCache.created_at) < self._clock() - CACHE_TTL
            )
        )


class _Settle:
    """Closes out one reservation: either gives it back, or records the tokens it used."""

    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        template: PromptTemplate,
        provider: str,
        reserved_at: datetime,
    ) -> None:
        self._args = (session, user_id, template.feature, provider, reserved_at)
        self._session = session

    async def refund(self) -> None:
        await budget.settle(*self._args, refund=True)
        await self._session.commit()

    async def tokens(self, input_tokens: int, output_tokens: int) -> None:
        await budget.settle(*self._args, input_tokens=input_tokens, output_tokens=output_tokens)
        await self._session.commit()
