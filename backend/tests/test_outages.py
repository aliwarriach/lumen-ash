"""What the API says when something it depends on is down."""

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_session
from app.main import DATABASE_DOWN, app


class _DeadSession:
    """A database session whose every call fails the way a dropped connection does."""

    def __getattr__(self, name: str) -> Any:
        async def fail(*args: Any, **kwargs: Any) -> Any:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        return fail


@pytest.fixture
def database_down() -> Iterator[None]:
    async def dead_session() -> AsyncIterator[Any]:
        yield _DeadSession()

    app.dependency_overrides[get_session] = dead_session
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(uuid.uuid4(), None)
    yield
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("path", ["/words", "/chapters", "/dashboard", "/ai/quota"])
def test_a_database_outage_is_a_503_that_says_what_is_wrong(
    client: TestClient, database_down: None, path: str
) -> None:
    response = client.get(path)
    # 503, not 500: the app retries it and shows the message instead of "the server had a problem".
    assert response.status_code == 503
    assert response.json() == {"detail": DATABASE_DOWN}
    assert response.headers["Retry-After"] == "30"
