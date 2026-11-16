from typing import Any

import httpx
import pytest

from app.coach.languagetool import LanguageToolClient, LanguageToolUnavailable, parse_matches

# Trimmed from a real response of https://api.languagetool.org/v2/check (language=de-DE).
OBJECT_AGREEMENT: dict[str, Any] = {
    "software": {"name": "LanguageTool", "version": "6.9-SNAPSHOT"},
    "matches": [
        {
            "message": "Prüfen Sie, ob hier der Akkusativ oder Dativ zu verwenden ist.",
            "replacements": [{"value": "einen Tisch"}],
            "offset": 9,
            "length": 9,
            "sentence": "Ich habe ein Tisch gekauft.",
            "rule": {
                "id": "OBJECT_AGREEMENT",
                "category": {"id": "GRAMMAR", "name": "Grammatik"},
                "confidence": 0.15,
            },
        }
    ],
}


def match(rule: str, category: str, replacements: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "message": "m",
        "offset": 0,
        "length": 3,
        "replacements": [{"value": r} for r in replacements],
        "rule": {"id": rule, "category": {"id": category}, **extra},
    }


def test_a_real_response_is_read_into_matches() -> None:
    (m,) = parse_matches(OBJECT_AGREEMENT)
    assert (m.start, m.end, m.rule_id, m.category) == (9, 18, "OBJECT_AGREEMENT", "GRAMMAR")
    assert m.replacements == ("einen Tisch",) and m.confidence == 0.15


def test_style_matches_and_matches_without_a_fix_are_left_out() -> None:
    payload = {
        "matches": [
            match("A", "STYLE", ["x"]),
            match("B", "TYPOGRAPHY", ["x"]),
            match("C", "GRAMMAR", []),
            match("D", "TYPOS", ["Hund", "Rund", "Bund", "Mund"]),
        ]
    }
    (m,) = parse_matches(payload)
    assert m.rule_id == "D" and m.replacements == ("Hund", "Rund", "Bund")  # at most three


def test_a_missing_confidence_is_none() -> None:
    (m,) = parse_matches({"matches": [match("D", "TYPOS", ["x"])]})
    assert m.confidence is None


def make(handler: Any, per_minute: int = 15, clock: Any = None) -> LanguageToolClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LanguageToolClient(
        http,
        "https://lt.test/v2/check",
        per_minute=per_minute,
        **({"clock": clock} if clock else {}),
    )


async def test_the_request_asks_for_german_and_sends_the_text_as_a_form() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=OBJECT_AGREEMENT)

    matches = await make(handler).check("Ich habe ein Tisch gekauft.")
    assert len(matches) == 1
    body = seen[0].content.decode()
    assert "language=de-DE" in body and "text=Ich+habe+ein+Tisch+gekauft." in body


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_errors_mean_languagetool_is_unavailable(status: int) -> None:
    client = make(lambda _: httpx.Response(status, text="no"))
    with pytest.raises(LanguageToolUnavailable):
        await client.check("Hallo")


async def test_timeouts_and_garbled_answers_mean_unavailable() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(LanguageToolUnavailable):
        await make(timeout).check("Hallo")
    with pytest.raises(LanguageToolUnavailable):
        await make(lambda _: httpx.Response(200, text="<html>")).check("Hallo")
    with pytest.raises(LanguageToolUnavailable):
        await make(
            lambda _: httpx.Response(
                200, json={"matches": [{"replacements": [{"value": "x"}], "rule": {}}]}
            )
        ).check("Hallo")


async def test_we_stay_under_the_public_apis_per_minute_limit_ourselves() -> None:
    now = [0.0]
    calls: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"matches": []})

    client = make(handler, per_minute=2, clock=lambda: now[0])
    await client.check("a")
    await client.check("b")
    with pytest.raises(LanguageToolUnavailable, match="limit"):
        await client.check("c")
    assert len(calls) == 2  # the third never left the building
    now[0] = 61.0
    await client.check("d")
