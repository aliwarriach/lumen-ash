import os

# Database tests need a throwaway Postgres: set TEST_DATABASE_URL (postgresql+psycopg://...).
# Without it, those tests are skipped and the rest still run.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

os.environ.update(
    ENVIRONMENT="test",
    SUPABASE_URL="https://test-project.supabase.co",
    DATABASE_URL=TEST_DATABASE_URL or "postgresql+psycopg://user:pass@localhost:5432/unused",
)

import uuid  # noqa: E402
from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, text  # noqa: E402

from app.core.auth import CurrentUser, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """Runs every migration down and up once per test session, then yields a sync engine."""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Engine]:
    """Empties every table after each test."""
    yield migrated_engine
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with migrated_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))


SwitchUser = Callable[[uuid.UUID], None]


@pytest.fixture
def as_user(db: Engine) -> Iterator[SwitchUser]:
    """Logs requests in as the given user id, skipping token checks."""
    current: dict[str, CurrentUser] = {}

    def switch(user_id: uuid.UUID) -> None:
        current["user"] = CurrentUser(id=user_id, email=f"{user_id}@example.com")

    switch(uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    yield switch
    app.dependency_overrides.pop(get_current_user, None)
