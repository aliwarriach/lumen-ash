import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.ai.budget import Limits, ProviderCeiling
from app.ai.errors import (
    AiBadResponseError,
    AiInputError,
    AiLimitError,
    AiUnavailableError,
    ProviderBadOutput,
    ProviderMisconfigured,
    ProviderRateLimited,
    ProviderUnavailable,
)
from app.ai.gateway import AiGateway, Cooldowns
from app.ai.models import AiCache, AiUsage
from app.ai.prompts import MESSAGE_CAPTURE, SENTENCE_COACH, Feature, SentenceCoachOut
from app.ai.providers import AiProvider, AiRequest, AiResponse

ANSWER = {"explanation": "Use einen with masculine nouns.", "practice": ["Ich sehe einen Hund."]}
CAPTURE_ANSWER = {"items": [{"kind": "homework", "text": "Seite 31", "due": "Freitag"}]}
TOKENS = (100, 50)

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


class FakeProvider:
    """Answers from a script. Each step is an answer dict or an exception to raise."""

    def __init__(self, name: str, *script: dict[str, Any] | Exception) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.script = list(script)
        self.requests: list[AiRequest] = []

    async def generate(self, request: AiRequest) -> AiResponse:
        self.requests.append(request)
        await asyncio.sleep(0)  # let concurrent callers interleave
        step = self.script.pop(0) if self.script else ANSWER
        if isinstance(step, Exception):
            raise step
        return AiResponse(step, TOKENS[0], TOKENS[1], self.name, self.model)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


def limits(**overrides: Any) -> Limits:
    base = Limits(
        user_requests=100,
        user_tokens=1_000_000,
        feature_requests={Feature.sentence_coach: 50, Feature.message_capture: 50},
        burst_per_minute=1000,
        provider={},
    )
    return replace(base, **overrides)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
async def sessions(db: Engine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def session(sessions: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with sessions() as s:
        yield s


def gateway(
    session: AsyncSession,
    providers: Sequence[AiProvider],
    clock: Clock,
    lim: Limits | None = None,
    cooldowns: Cooldowns | None = None,
    **kwargs: Any,
) -> AiGateway:
    return AiGateway(
        session, providers, lim or limits(), cooldowns or Cooldowns(), clock=clock, **kwargs
    )


def sentence(text: str = "Ich habe ein Tisch gekauft.") -> dict[str, str]:
    return {"sentence": text, "findings": "article", "topics": "accusative"}


async def usage_rows(session: AsyncSession, user: uuid.UUID) -> dict[str, tuple[int, int]]:
    """provider -> (requests, tokens) for the learner."""
    rows = await session.execute(
        select(
            AiUsage.provider,
            func.sum(AiUsage.requests),
            func.sum(AiUsage.input_tokens + AiUsage.output_tokens),
        )
        .where(AiUsage.user_id == user)
        .group_by(AiUsage.provider)
    )
    return {p: (int(r), int(t)) for p, r, t in rows}


# --- the happy path ---------------------------------------------------------------------------


async def test_a_call_returns_validated_output_and_records_the_providers_token_counts(
    session: AsyncSession, clock: Clock
) -> None:
    gemini = FakeProvider("gemini")
    result = await gateway(session, [gemini], clock).run(ALICE, SENTENCE_COACH, sentence())

    assert isinstance(result.output, SentenceCoachOut)
    assert result.output.practice == ["Ich sehe einen Hund."]
    assert (result.cached, result.provider) == (False, "gemini")
    assert await usage_rows(session, ALICE) == {"gemini": (1, 150)}
    request = gemini.requests[0]
    assert request.max_output_tokens == SENTENCE_COACH.max_output_tokens
    assert "Reply with JSON only" in request.system
    assert "Ich habe ein Tisch gekauft." in request.user


async def test_each_template_has_its_own_output_shape(session: AsyncSession, clock: Clock) -> None:
    provider = FakeProvider("gemini", CAPTURE_ANSWER)
    result = await gateway(session, [provider], clock).run(
        ALICE, MESSAGE_CAPTURE, {"message": "Hausaufgabe: Seite 31 bis Freitag"}
    )
    assert result.output.model_dump()["items"][0]["due"] == "Freitag"


# --- limits: one learner is blocked, others are not ---------------------------------------------


async def test_a_learner_at_their_daily_limit_is_blocked_and_others_are_unaffected(
    session: AsyncSession, clock: Clock
) -> None:
    provider = FakeProvider("gemini")
    gw = gateway(session, [provider], clock, limits(user_requests=2))
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 1"))
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 2"))

    with pytest.raises(AiLimitError) as blocked:
        await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 3"))
    assert blocked.value.code == "daily_limit"
    assert blocked.value.status_code == 429
    assert blocked.value.resets_at == datetime(2026, 11, 12, tzinfo=UTC)
    assert len(provider.requests) == 2  # the blocked call never reached the provider

    await gw.run(BOB, SENTENCE_COACH, sentence("Satz 3"))  # someone else is fine
    assert len(provider.requests) == 3

    clock.advance(hours=13)  # past midnight UTC: nothing to reset, it's a new date
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 4"))


async def test_a_feature_cap_blocks_only_that_feature(session: AsyncSession, clock: Clock) -> None:
    provider = FakeProvider("gemini")
    gw = gateway(
        session,
        [provider],
        clock,
        limits(feature_requests={Feature.sentence_coach: 1, Feature.message_capture: 5}),
    )
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 1"))
    with pytest.raises(AiLimitError) as blocked:
        await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 2"))
    assert blocked.value.code == "feature_limit"
    assert "sentence checks" in blocked.value.message

    provider.script.append(CAPTURE_ANSWER)
    await gw.run(ALICE, MESSAGE_CAPTURE, {"message": "Hausaufgabe"})


async def test_the_token_limit_stops_a_learner_once_it_has_been_passed(
    session: AsyncSession, clock: Clock
) -> None:
    # Each call uses 150 tokens. Tokens are only known after the call, so the call that crosses
    # the limit still goes through; the one after it is blocked.
    gw = gateway(session, [FakeProvider("gemini")], clock, limits(user_tokens=200))
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 1"))  # 150 < 200: allowed
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 2"))  # 150 < 200 at the start: allowed
    with pytest.raises(AiLimitError) as blocked:
        await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 3"))  # 300 >= 200
    assert blocked.value.code == "daily_limit"


async def test_the_burst_throttle_blocks_rapid_requests_and_recovers(
    session: AsyncSession, clock: Clock
) -> None:
    provider = FakeProvider("gemini")
    gw = gateway(session, [provider], clock, limits(burst_per_minute=3))
    for i in range(3):
        await gw.run(ALICE, SENTENCE_COACH, sentence(f"Satz {i}"))

    with pytest.raises(AiLimitError) as blocked:
        await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 3"))
    assert blocked.value.code == "too_fast"
    assert blocked.value.retry_after_seconds == 61  # the window started this second
    assert len(provider.requests) == 3

    await gw.run(BOB, SENTENCE_COACH, sentence("Satz 3"))  # other learners aren't throttled
    cached = await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 0"))  # cache hits are free
    assert cached.cached

    clock.advance(seconds=61)
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 3"))


async def test_concurrent_requests_cannot_slip_past_a_limit(
    sessions: async_sessionmaker[AsyncSession], clock: Clock
) -> None:
    provider = FakeProvider("gemini")
    lim = limits(user_requests=3)

    async def attempt(i: int) -> str:
        async with sessions() as s:
            try:
                await gateway(s, [provider], clock, lim).run(
                    ALICE, SENTENCE_COACH, sentence(f"Satz {i}")
                )
            except AiLimitError as exc:
                return exc.code
            return "ok"

    outcomes = await asyncio.gather(*(attempt(i) for i in range(10)))
    assert sorted(outcomes) == ["daily_limit"] * 7 + ["ok"] * 3
    assert len(provider.requests) == 3


# --- shared ceilings and fallback ---------------------------------------------------------------


async def test_a_provider_at_its_shared_ceiling_is_skipped(
    session: AsyncSession, clock: Clock
) -> None:
    gemini, groq = FakeProvider("gemini"), FakeProvider("groq")
    lim = limits(provider={"gemini": ProviderCeiling(requests=2)})
    gw = gateway(session, [gemini, groq], clock, lim)

    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 1"))
    await gw.run(BOB, SENTENCE_COACH, sentence("Satz 2"))  # gemini now at 2 requests across users
    result = await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 3"))

    assert result.provider == "groq"
    assert len(gemini.requests) == 2 and len(groq.requests) == 1


async def test_a_token_ceiling_also_skips_a_provider(session: AsyncSession, clock: Clock) -> None:
    gemini, groq = FakeProvider("gemini"), FakeProvider("groq")
    lim = limits(provider={"gemini": ProviderCeiling(tokens=150)})
    gw = gateway(session, [gemini, groq], clock, lim)
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 1"))  # uses 150 tokens
    assert (await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 2"))).provider == "groq"


async def test_when_every_provider_is_at_its_ceiling_the_error_says_so(
    session: AsyncSession, clock: Clock
) -> None:
    lim = limits(
        provider={"gemini": ProviderCeiling(requests=0), "groq": ProviderCeiling(requests=0)}
    )
    gemini, groq = FakeProvider("gemini"), FakeProvider("groq")
    with pytest.raises(AiUnavailableError) as blocked:
        await gateway(session, [gemini, groq], clock, lim).run(ALICE, SENTENCE_COACH, sentence())
    assert blocked.value.code == "shared_limit"
    assert not gemini.requests and not groq.requests


async def test_a_rate_limited_provider_falls_back_and_the_learner_is_not_charged_for_it(
    session: AsyncSession, clock: Clock
) -> None:
    gemini = FakeProvider("gemini", ProviderRateLimited("quota", retry_after_seconds=30))
    groq = FakeProvider("groq")
    cooldowns = Cooldowns()
    gw = gateway(session, [gemini, groq], clock, cooldowns=cooldowns)

    result = await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 1"))
    assert result.provider == "groq"
    assert await usage_rows(session, ALICE) == {"gemini": (0, 0), "groq": (1, 150)}

    # Gemini is left alone while it cools down, then tried again.
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 2"))
    assert len(gemini.requests) == 1
    clock.advance(seconds=31)
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 3"))
    assert len(gemini.requests) == 2


async def test_an_outage_also_falls_back(session: AsyncSession, clock: Clock) -> None:
    gemini = FakeProvider("gemini", ProviderUnavailable("HTTP 503"))
    result = await gateway(session, [gemini, FakeProvider("groq")], clock).run(
        ALICE, SENTENCE_COACH, sentence()
    )
    assert result.provider == "groq"


async def test_the_provider_order_decides_who_is_asked_first(
    session: AsyncSession, clock: Clock
) -> None:
    gemini, groq = FakeProvider("gemini"), FakeProvider("groq")
    result = await gateway(session, [groq, gemini], clock).run(ALICE, SENTENCE_COACH, sentence())
    assert result.provider == "groq" and not gemini.requests


async def test_when_both_providers_are_unavailable_the_learner_gets_a_clean_error_and_no_charge(
    session: AsyncSession, clock: Clock
) -> None:
    gemini = FakeProvider("gemini", ProviderRateLimited("quota"))
    groq = FakeProvider("groq", ProviderUnavailable("timeout"))
    gw = gateway(session, [gemini, groq], clock)

    with pytest.raises(AiUnavailableError) as blocked:
        await gw.run(ALICE, SENTENCE_COACH, sentence())
    assert blocked.value.code == "unavailable" and blocked.value.status_code == 503
    assert await usage_rows(session, ALICE) == {"gemini": (0, 0), "groq": (0, 0)}

    # Both are cooling down, so the next try doesn't hammer them.
    with pytest.raises(AiUnavailableError):
        await gw.run(ALICE, SENTENCE_COACH, sentence())
    assert len(gemini.requests) == 1 and len(groq.requests) == 1


async def test_with_no_provider_configured_ai_is_simply_unavailable(
    session: AsyncSession, clock: Clock
) -> None:
    with pytest.raises(AiUnavailableError):
        await gateway(session, [], clock).run(ALICE, SENTENCE_COACH, sentence())


# --- the cache ----------------------------------------------------------------------------------


async def test_the_same_sentence_is_never_paid_for_twice(
    session: AsyncSession, clock: Clock
) -> None:
    provider = FakeProvider("gemini")
    gw = gateway(session, [provider], clock, limits(user_requests=1))

    first = await gw.run(ALICE, SENTENCE_COACH, sentence("Ich habe ein Tisch gekauft."))
    again = await gw.run(ALICE, SENTENCE_COACH, sentence("  Ich habe  ein Tisch gekauft.\n"))
    other_user = await gw.run(BOB, SENTENCE_COACH, sentence("Ich habe ein Tisch gekauft."))

    assert (first.cached, again.cached, other_user.cached) == (False, True, True)
    assert again.provider is None and again.output == first.output
    assert len(provider.requests) == 1
    assert await usage_rows(session, ALICE) == {"gemini": (1, 150)}  # unchanged by the hit
    assert await usage_rows(session, BOB) == {}
    cache = (await session.scalars(select(AiCache))).one()
    assert (cache.hits, cache.provider, cache.model) == (2, "gemini", "gemini-model")


async def test_a_cached_answer_is_still_served_to_a_learner_who_is_out_of_requests(
    session: AsyncSession, clock: Clock
) -> None:
    gw = gateway(session, [FakeProvider("gemini")], clock, limits(user_requests=1))
    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 1"))
    assert (await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 1"))).cached
    with pytest.raises(AiLimitError):
        await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 2"))


async def test_case_matters_and_a_new_template_version_misses_the_cache(
    session: AsyncSession, clock: Clock
) -> None:
    provider = FakeProvider("gemini")
    gw = gateway(session, [provider], clock)
    await gw.run(ALICE, SENTENCE_COACH, sentence("ich habe einen tisch"))
    await gw.run(ALICE, SENTENCE_COACH, sentence("Ich habe einen Tisch"))  # capitals are the point
    await gw.run(
        ALICE,
        replace(SENTENCE_COACH, version=SENTENCE_COACH.version + 1),
        sentence("Ich habe einen Tisch"),
    )
    assert len(provider.requests) == 3


async def test_a_cached_answer_that_no_longer_fits_the_schema_is_replaced(
    session: AsyncSession, clock: Clock
) -> None:
    provider = FakeProvider("gemini")
    gw = gateway(session, [provider], clock)
    await gw.run(ALICE, SENTENCE_COACH, sentence())
    row = (await session.scalars(select(AiCache))).one()
    row.response = {"old_shape": True}
    await session.commit()

    result = await gw.run(ALICE, SENTENCE_COACH, sentence())
    assert not result.cached and len(provider.requests) == 2
    stored = (await session.scalars(select(AiCache))).one().response
    assert SentenceCoachOut.model_validate(stored) == SentenceCoachOut.model_validate(ANSWER)


async def test_cached_answers_nobody_has_asked_for_in_30_days_are_deleted(
    session: AsyncSession, clock: Clock
) -> None:
    """Cached answers are made from what the learner wrote, so they don't live for ever."""
    gw = gateway(session, [FakeProvider("gemini")], clock)
    for n in range(3):
        await gw.run(ALICE, SENTENCE_COACH, sentence(f"Satz {n}"))
    unused, used_lately, fresh = (
        await session.scalars(select(AiCache).order_by(AiCache.key))
    ).all()
    unused.created_at = clock.now - timedelta(days=45)  # never asked for again
    used_lately.created_at = clock.now - timedelta(days=45)
    used_lately.last_hit_at = clock.now - timedelta(days=3)  # old, but still being used
    fresh.created_at = clock.now - timedelta(days=1)
    await session.commit()
    keep = {used_lately.key, fresh.key}

    await gw.run(ALICE, SENTENCE_COACH, sentence("Satz 99"))  # a miss: a new answer is stored

    keys = set(await session.scalars(select(AiCache.key)))
    assert unused.key not in keys
    assert keep <= keys and len(keys) == 3


# --- bad answers, privacy and input size --------------------------------------------------------


async def test_unusable_output_is_a_clean_error_that_is_not_cached(
    session: AsyncSession, clock: Clock
) -> None:
    provider = FakeProvider("gemini", {"explanation": "ok"}, ProviderBadOutput("cut off", 40, 350))
    gw = gateway(session, [provider], clock, cooldowns=Cooldowns())

    for _ in range(2):  # a wrong shape, then a cut-off answer
        with pytest.raises(AiBadResponseError) as bad:
            await gw.run(ALICE, SENTENCE_COACH, sentence())
        assert bad.value.status_code == 502

    assert (await session.scalars(select(AiCache))).all() == []
    # The provider spent tokens on both, so both stay counted.
    assert await usage_rows(session, ALICE) == {"gemini": (2, 150 + 390)}


async def test_a_bad_answer_from_one_provider_is_tried_again_with_the_next(
    session: AsyncSession, clock: Clock
) -> None:
    first = FakeProvider("groq", ProviderBadOutput("cut off", 40, 350), {"explanation": "ok"})
    second = FakeProvider("gemini")
    cooldowns = Cooldowns()
    gw = gateway(session, [first, second], clock, cooldowns=cooldowns)

    for _ in range(2):  # a cut-off answer, then a wrong shape
        clock.advance(seconds=1)
        result = await gw.run(ALICE, SENTENCE_COACH, sentence(f"Satz {clock.now.second}."))
        assert result.provider == "gemini"

    # A bad answer is not an outage: the first provider is asked again next time.
    assert not cooldowns.active("groq", clock.now)
    assert len(first.requests) == 2
    # The first provider's tokens were spent, so they stay counted.
    assert await usage_rows(session, ALICE) == {"groq": (2, 150 + 390), "gemini": (2, 300)}


async def test_a_misconfigured_provider_is_left_alone_for_ten_minutes(
    session: AsyncSession, clock: Clock
) -> None:
    broken = FakeProvider("gemini", ProviderMisconfigured("gemini: HTTP 402 (no credit)"))
    working = FakeProvider("groq")
    gw = gateway(session, [broken, working], clock, cooldowns=Cooldowns())

    for minute in range(10):  # one failed try, then nine minutes of going straight to groq
        result = await gw.run(ALICE, SENTENCE_COACH, sentence(f"Satz {minute}."))
        assert result.provider == "groq"
        clock.advance(minutes=1)
    assert len(broken.requests) == 1

    clock.advance(seconds=1)  # ten minutes on it is given another chance, and has been fixed
    result = await gw.run(ALICE, SENTENCE_COACH, sentence("Noch ein Satz."))
    assert result.provider == "gemini"
    # The failed try cost the learner nothing.
    assert await usage_rows(session, ALICE) == {"groq": (10, 10 * 150), "gemini": (1, 150)}


async def test_personal_details_are_removed_before_anything_is_sent_or_cached(
    session: AsyncSession, clock: Clock
) -> None:
    provider = FakeProvider("gemini")
    gw = gateway(session, [provider], clock, redact_names=["Sara"])

    text = "Sara ruft +92 300 1234567 an. Mail: sara@example.com"
    await gw.run(ALICE, SENTENCE_COACH, sentence(text), extra_names=["Müller"])
    sent = provider.requests[0].user
    assert "Sara" not in sent and "1234567" not in sent and "example.com" not in sent
    assert "[name]" in sent and "[phone]" in sent and "[email]" in sent

    # A different number gives the same redacted prompt, so it's the same cache entry.
    same = await gw.run(ALICE, SENTENCE_COACH, sentence(text.replace("1234567", "7654321")))
    assert same.cached
    cached_text = str((await session.scalars(select(AiCache))).one().response)
    assert "Sara" not in cached_text


async def test_text_over_the_input_cap_is_rejected_before_any_call_or_charge(
    session: AsyncSession, clock: Clock
) -> None:
    provider = FakeProvider("gemini")
    with pytest.raises(AiInputError) as too_long:
        await gateway(session, [provider], clock).run(
            ALICE, SENTENCE_COACH, sentence("Wort " * 1000)
        )
    assert too_long.value.status_code == 422
    assert not provider.requests and await usage_rows(session, ALICE) == {}
