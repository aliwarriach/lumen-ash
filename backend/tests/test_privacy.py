from typing import Any

import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app.main import sentry_options


def test_sentry_is_told_not_to_send_what_the_learner_wrote() -> None:
    options = sentry_options("https://key@o0.ingest.sentry.io/1", "production")
    assert options["max_request_body_size"] == "never"
    assert options["include_local_variables"] is False
    assert options["send_default_pii"] is False
    assert options["traces_sample_rate"] == 0.0


class CapturingTransport(Transport):
    def __init__(self, options: dict[str, Any]) -> None:
        super().__init__(options)
        self.events: list[Any] = []

    def capture_envelope(self, envelope: Any) -> None:
        if envelope.get_event() is not None:
            self.events.append(envelope.get_event())


def test_an_error_report_from_a_request_holds_no_request_body_and_no_local_variables() -> None:
    """The real thing: crash a request that carries a secret and read what Sentry would send."""
    secret = "Frau Schmidt +92 300 1234567 Hausaufgabe"
    transport = CapturingTransport({})
    sentry_sdk.init(
        transport=transport, **sentry_options("https://key@o0.ingest.sentry.io/1", "test")
    )
    try:
        app = FastAPI()

        @app.post("/boom")
        async def boom(body: dict[str, str]) -> None:
            message = body["text"]  # a local variable holding the secret
            raise RuntimeError(f"failed on {len(message)} characters")

        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post("/boom", json={"text": secret}).status_code == 500
        sentry_sdk.flush()
    finally:
        sentry_sdk.init()  # switch Sentry off again for the other tests

    assert transport.events, "the error should have been reported"
    sent = repr(transport.events)
    assert "Schmidt" not in sent and "1234567" not in sent and secret not in sent


# --- What reaches the database -------------------------------------------------------------------

from sqlalchemy import JSON, Engine, String, Text, text  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402

from app.coach.deps import get_languagetool  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from tests.conftest import SwitchUser  # noqa: E402
from tests.test_ai_gateway import FakeProvider  # noqa: E402
from tests.test_capture_api import AI_ANSWER as CAPTURE_ANSWER  # noqa: E402
from tests.test_capture_api import MESSAGE, reset_overrides, save, scan  # noqa: E402
from tests.test_capture_api import setup as capture_setup  # noqa: E402
from tests.test_coach_api import AI_ANSWER as COACH_ANSWER  # noqa: E402
from tests.test_coach_api import FakeLanguageTool, check  # noqa: E402
from tests.test_coach_api import setup as coach_setup  # noqa: E402
from tests.test_review_api import Clock, clock  # noqa: E402

__all__ = ["clock", "reset_overrides"]  # fixtures, re-used from the other test modules

# Things from a class chat or a sentence that must never be written to the database.
NAME = "Schmidt"  # the sender's name in the message's "[time] Name:" prefix
PHONE = "1234567"  # part of a phone number in the message
EMAIL = "ali.khan@example.com"
SENTENCE = f"Ich habe ein Tisch gekauft, schreib mir an {EMAIL} oder ruf +92 300 {PHONE} an."


def occurrences(db: Engine, needle: str) -> list[str]:
    """Every `table.column` whose stored text contains `needle`, found by scanning all of them."""
    found = []
    with db.connect() as conn:
        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if not isinstance(column.type, String | Text | JSON | JSONB):
                    continue
                n = conn.execute(
                    text(
                        f'SELECT count(*) FROM "{table.name}" WHERE "{column.name}"::text LIKE :p'
                    ),
                    {"p": f"%{needle}%"},
                ).scalar_one()
                if n:
                    found.append(f"{table.name}.{column.name}")
    return found


def test_no_classmate_detail_from_a_message_or_sentence_is_stored_anywhere(
    client: TestClient, as_user: SwitchUser, clock: Clock, db: Engine
) -> None:
    """Scan a class message, approve its tasks, and run a writing check; then search every text
    column of every table for the name, the phone number and the email."""
    capture_setup(FakeProvider("gemini", CAPTURE_ANSWER))
    proposed = scan(client, MESSAGE)
    save(client, *[{"title": i["title"], "due_date": i["due_date"]} for i in proposed["items"]])

    coach_setup(FakeLanguageTool(), FakeProvider("gemini", COACH_ANSWER))
    try:
        stored = check(client, SENTENCE)["text"]
    finally:
        app.dependency_overrides.pop(get_languagetool, None)

    assert EMAIL not in stored and PHONE not in stored  # the check keeps the redacted text
    for secret in (NAME, PHONE, EMAIL, "+92"):
        assert occurrences(db, secret) == [], f"{secret!r} was stored"
    # The search itself works: it does find what we do keep.
    assert "class_tasks.title" in occurrences(db, "Arbeitsbuch Seite 24")
    assert "coach_checks.text" in occurrences(db, "Tisch")
