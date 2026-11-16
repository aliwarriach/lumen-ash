import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.deps import get_providers
from app.ai.errors import AiBadResponseError, AiLimitError, AiUnavailableError
from app.ai.providers import AiProvider
from app.main import app
from tests.conftest import SwitchUser
from tests.test_ai_gateway import FakeProvider


@app.get("/_test/ai-error/{kind}", include_in_schema=False)
async def raise_ai_error(kind: str) -> None:
    """Test-only route: proves each AiError becomes a clean JSON response."""
    if kind == "too_fast":
        raise AiLimitError("too_fast", "Slow down.", retry_after_seconds=12)
    if kind == "daily":
        raise AiLimitError("daily_limit", "All used.", resets_at=datetime(2026, 11, 12, tzinfo=UTC))
    if kind == "bad":
        raise AiBadResponseError("Unusable.")
    raise AiUnavailableError("Down.")


def set_providers(*providers: AiProvider) -> None:
    app.dependency_overrides[get_providers] = lambda: providers


@pytest.fixture(autouse=True)
def gemini_and_groq() -> Iterator[None]:
    set_providers(FakeProvider("gemini"), FakeProvider("groq"))
    yield
    app.dependency_overrides.pop(get_providers, None)


def add_usage(
    db: Engine, user: uuid.UUID, feature: str, requests: int, provider: str = "gemini"
) -> None:
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ai_usage (user_id, usage_date, feature, provider, requests,"
                " input_tokens, output_tokens) VALUES (:u, :d, :f, :p, :r, 0, 0)"
            ),
            {"u": user, "d": datetime.now(UTC).date(), "f": feature, "p": provider, "r": requests},
        )


def remaining(client: TestClient) -> dict[str, int]:
    body = client.get("/ai/quota").json()
    return {f["feature"]: f["remaining"] for f in body["features"]}


def test_quota_requires_login(client: TestClient) -> None:
    assert client.get("/ai/quota").status_code == 401


def test_a_new_learner_sees_the_full_allowance(client: TestClient, as_user: SwitchUser) -> None:
    body = client.get("/ai/quota").json()
    assert body["available"] is True
    assert body["resets_at"].endswith("Z") or body["resets_at"].endswith("+00:00")
    assert datetime.fromisoformat(body["resets_at"]).hour == 0
    sentence = next(f for f in body["features"] if f["feature"] == "sentence_coach")
    assert sentence == {
        "feature": "sentence_coach",
        "label": "sentence checks",
        "limit": 25,
        "used": 0,
        "remaining": 25,
    }


def test_remaining_counts_down_per_learner(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    alice, bob = uuid.uuid4(), uuid.uuid4()
    add_usage(db, alice, "sentence_coach", 3)
    add_usage(db, bob, "sentence_coach", 20)

    as_user(alice)
    assert remaining(client)["sentence_coach"] == 22
    assert remaining(client)["message_capture"] == 10
    as_user(bob)
    assert remaining(client)["sentence_coach"] == 5


def test_the_overall_daily_limit_caps_every_feature(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    user = uuid.uuid4()
    as_user(user)
    add_usage(db, user, "sentence_coach", 25)
    add_usage(db, user, "message_capture", 15)  # 40 in total = the default daily limit
    assert remaining(client) == {"sentence_coach": 0, "message_capture": 0, "exercise_help": 0}


def test_ai_shows_as_unavailable_with_no_provider_or_when_all_are_at_their_ceiling(
    client: TestClient, as_user: SwitchUser, db: Engine
) -> None:
    set_providers()
    assert client.get("/ai/quota").json()["available"] is False

    set_providers(FakeProvider("gemini"), FakeProvider("groq"))
    add_usage(db, uuid.uuid4(), "sentence_coach", 400, provider="gemini")  # gemini's ceiling
    assert client.get("/ai/quota").json()["available"] is True  # groq still has room

    set_providers(FakeProvider("gemini"))
    assert client.get("/ai/quota").json()["available"] is False


def test_ai_errors_become_clean_json_not_500s(client: TestClient) -> None:
    slow = client.get("/_test/ai-error/too_fast")
    assert slow.status_code == 429
    assert slow.headers["retry-after"] == "12"
    assert slow.json() == {
        "detail": {
            "code": "too_fast",
            "message": "Slow down.",
            "retry_after_seconds": 12,
            "resets_at": None,
        }
    }

    daily = client.get("/_test/ai-error/daily")
    assert daily.status_code == 429
    assert daily.json()["detail"]["code"] == "daily_limit"
    assert daily.json()["detail"]["resets_at"].startswith("2026-11-12")

    assert client.get("/_test/ai-error/bad").status_code == 502
    down = client.get("/_test/ai-error/down")
    assert (down.status_code, down.json()["detail"]["code"]) == (503, "unavailable")
