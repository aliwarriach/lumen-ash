import time
import uuid
from collections.abc import Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core import auth

# The real one: the autouse fixture below swaps the module's attribute for a fake.
REAL_GET_JWKS_CLIENT = auth.get_jwks_client

ISSUER = "https://test-project.supabase.co/auth/v1"
USER_ID = str(uuid.uuid4())


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeSigningKey:
    def __init__(self, key: Any) -> None:
        self.key = key


class _FakeJWKSClient:
    def __init__(self, public_key: Any) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        if jwt.get_unverified_header(token).get("kid") != "test-kid":
            raise jwt.PyJWKClientError("unknown kid")
        return _FakeSigningKey(self._public_key)


@pytest.fixture(autouse=True)
def fake_jwks(monkeypatch: pytest.MonkeyPatch, private_key: rsa.RSAPrivateKey) -> Iterator[None]:
    monkeypatch.setattr(auth, "get_jwks_client", lambda: _FakeJWKSClient(private_key.public_key()))
    yield


def make_token(private_key: rsa.RSAPrivateKey, kid: str = "test-kid", **overrides: Any) -> str:
    now = int(time.time())
    claims = {
        "sub": USER_ID,
        "email": "learner@example.com",
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
        **overrides,
    }
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def get_me(client: TestClient, token: str | None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/me", headers=headers)


def test_valid_token_returns_user(client: TestClient, private_key: rsa.RSAPrivateKey) -> None:
    response = get_me(client, make_token(private_key))
    assert response.status_code == 200
    assert response.json() == {"id": USER_ID, "email": "learner@example.com"}


def test_missing_token_rejected(client: TestClient) -> None:
    assert get_me(client, None).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 10},
        {"aud": "anon"},
        {"iss": "https://someone-else.supabase.co/auth/v1"},
        {"sub": "not-a-uuid"},
    ],
    ids=["expired", "wrong-audience", "wrong-issuer", "bad-subject"],
)
def test_bad_claims_rejected(
    client: TestClient, private_key: rsa.RSAPrivateKey, overrides: dict[str, Any]
) -> None:
    assert get_me(client, make_token(private_key, **overrides)).status_code == 401


def test_unknown_key_rejected(client: TestClient, private_key: rsa.RSAPrivateKey) -> None:
    assert get_me(client, make_token(private_key, kid="other")).status_code == 401


def test_token_signed_by_other_key_rejected(client: TestClient) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert get_me(client, make_token(other)).status_code == 401


def test_symmetric_token_rejected(client: TestClient) -> None:
    now = int(time.time())
    token = jwt.encode(
        {"sub": USER_ID, "aud": "authenticated", "iss": ISSUER, "exp": now + 60},
        "a-shared-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
        headers={"kid": "test-kid"},
    )
    assert get_me(client, token).status_code == 401


def test_not_reaching_supabase_is_our_outage_not_a_bad_login(
    client: TestClient, private_key: rsa.RSAPrivateKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Unreachable:
        def get_signing_key_from_jwt(self, token: str) -> Any:
            raise jwt.PyJWKClientConnectionError("Fail to fetch data from the url")

    monkeypatch.setattr(auth, "get_jwks_client", lambda: _Unreachable())
    response = get_me(client, make_token(private_key))
    # 401 would tell the app the learner is signed out, and it would discard queued answers.
    assert response.status_code == 503
    assert "try again" in response.json()["detail"]


def test_the_real_signing_key_client_trusts_the_usual_certificate_authorities() -> None:
    # Python from python.org has no root certificates of its own until "Install Certificates" is
    # run, so urllib (which PyJWT uses) failed every HTTPS fetch of Supabase's keys on such a
    # Mac: every request was a 503 "sign-in service can't be reached". The client brings its own.
    REAL_GET_JWKS_CLIENT.cache_clear()
    try:
        client = REAL_GET_JWKS_CLIENT()
        assert client.ssl_context is not None
        assert client.ssl_context.cert_store_stats()["x509_ca"] > 100
        assert client.ssl_context.verify_mode.name == "CERT_REQUIRED"
    finally:
        REAL_GET_JWKS_CLIENT.cache_clear()
