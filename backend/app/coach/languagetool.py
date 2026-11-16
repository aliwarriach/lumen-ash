"""A small client for LanguageTool's public API (free, rule-based, no AI).

What we send is the learner's already-redacted sentence. The public API is shared and limited
(about 20 requests a minute per IP), so we keep our own count a little below that and treat any
failure as "LanguageTool isn't available": the coach carries on without it.
"""

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

# Categories that are about style or typography, not the A1 mistakes we coach.
IGNORED_CATEGORIES = frozenset(
    {
        "STYLE",
        "REDUNDANCY",
        "COLLOQUIALISMS",
        "PLAIN_ENGLISH",
        "CREATIVE_WRITING",
        "GENDER_NEUTRALITY",
        "WIKIPEDIA",
        "BARRIEREFREI",
        "TYPOGRAPHY",
        "PUNCTUATION",
    }
)
MAX_REPLACEMENTS = 3


class LanguageToolUnavailable(Exception):
    """Rate limited, down, slow, or answered with something we can't read."""


@dataclass(frozen=True)
class LtMatch:
    start: int
    end: int
    rule_id: str
    category: str
    message: str  # in German: not shown to the learner unless nothing better exists
    replacements: tuple[str, ...]
    confidence: float | None  # LanguageTool's own estimate, when it gives one


def parse_matches(payload: dict[str, Any]) -> list[LtMatch]:
    matches = []
    for m in payload.get("matches") or []:
        rule = m.get("rule") or {}
        category = (rule.get("category") or {}).get("id", "")
        replacements = tuple(
            r["value"] for r in (m.get("replacements") or [])[:MAX_REPLACEMENTS] if r.get("value")
        )
        if category in IGNORED_CATEGORIES or not replacements:
            continue  # with no suggested fix there is no correction to offer
        confidence = rule.get("confidence")
        matches.append(
            LtMatch(
                start=int(m["offset"]),
                end=int(m["offset"]) + int(m["length"]),
                rule_id=str(rule.get("id", "")),
                category=str(category),
                message=str(m.get("message", "")),
                replacements=replacements,
                confidence=float(confidence) if isinstance(confidence, int | float) else None,
            )
        )
    return matches


class LanguageToolClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        url: str,
        timeout_seconds: float = 10.0,
        per_minute: int = 15,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._url = url
        self._timeout = timeout_seconds
        self._per_minute = per_minute
        self._clock = clock
        self._recent: deque[float] = deque()

    def _room(self) -> bool:
        now = self._clock()
        while self._recent and now - self._recent[0] >= 60:
            self._recent.popleft()
        if len(self._recent) >= self._per_minute:
            return False
        self._recent.append(now)
        return True

    async def check(self, text: str) -> list[LtMatch]:
        if not self._room():
            raise LanguageToolUnavailable("over our own per-minute limit")
        try:
            response = await self._client.post(
                self._url,
                data={"language": "de-DE", "motherTongue": "en", "text": text},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LanguageToolUnavailable(type(exc).__name__) from exc
        if response.status_code != 200:
            raise LanguageToolUnavailable(f"HTTP {response.status_code}")
        try:
            payload = response.json()
            return parse_matches(payload)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise LanguageToolUnavailable("unreadable response") from exc
