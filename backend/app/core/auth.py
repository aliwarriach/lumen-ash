"""Supabase login-token verification.

The app logs in with Supabase and sends the access token as `Authorization: Bearer <token>`.
We verify it against the project's public signing keys (JWKS). No shared secret is stored here.
"""

import ssl
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import certifi
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)

ALLOWED_ALGORITHMS = ["RS256", "ES256"]


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None


@lru_cache
def get_jwks_client() -> jwt.PyJWKClient:
    # PyJWKClient caches keys and refetches when it sees an unknown key id. The default wait of
    # 30 seconds would leave the app's own one-minute limit almost used up before we answer.
    #
    # The keys are fetched with urllib, which trusts only the root certificates Python itself
    # finds. Python from python.org has none until its "Install Certificates" step is run, so
    # every fetch failed and every request became a 503. Bring certifi's bundle (httpx's own).
    return jwt.PyJWKClient(
        get_settings().supabase_jwks_url,
        cache_keys=True,
        lifespan=3600,
        timeout=10,
        ssl_context=ssl.create_default_context(cafile=certifi.where()),
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@dataclass(frozen=True)
class VerifiedToken:
    user: CurrentUser
    expires_at: int  # Unix seconds, from the token's `exp`


class TokenRejected(Exception):
    """The token is not a login we accept. The message is safe to show."""


class SignInServiceDown(Exception):
    """Supabase's signing keys couldn't be fetched, so the token can't be judged either way."""


def verify_token(token: str) -> VerifiedToken:
    """Checks a Supabase access token. Blocking (it may fetch the signing keys): call it from a
    thread. Used by every request and by the community socket, which has no request headers."""
    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            audience="authenticated",
            issuer=get_settings().supabase_issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.PyJWKClientConnectionError as exc:
        raise SignInServiceDown from exc
    except jwt.PyJWKClientError as exc:
        raise TokenRejected("Unknown signing key") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenRejected("Invalid or expired token") from exc

    try:
        user_id = UUID(claims["sub"])
    except ValueError as exc:
        raise TokenRejected("Invalid subject") from exc

    return VerifiedToken(
        user=CurrentUser(id=user_id, email=claims.get("email")), expires_at=int(claims["exp"])
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    # A plain `def` on purpose: FastAPI runs it in a thread, so the JWKS fetch doesn't block.
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    try:
        return verify_token(credentials.credentials).user
    except SignInServiceDown as exc:
        # We couldn't fetch Supabase's signing keys, so we can't tell whether the token is good.
        # That is our outage, not a bad login: saying 401 would make the app treat the learner as
        # signed out and throw away the answers it is waiting to upload.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sign-in service can't be reached right now. Please try again in a minute.",
            headers={"Retry-After": "30"},
        ) from exc
    except TokenRejected as exc:
        raise _unauthorized(str(exc)) from exc


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
