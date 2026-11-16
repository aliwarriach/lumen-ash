import logging
from typing import Any

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.ai.errors import AiError
from app.ai.router import ai_error_handler
from app.ai.router import router as ai_router
from app.api import router
from app.capture.router import router as capture_router
from app.coach.router import router as coach_router
from app.community.router import router as community_router
from app.core.config import get_settings
from app.course.router import router as course_router
from app.dashboard.router import router as dashboard_router
from app.dictionary.router import router as dictionary_router
from app.exams.router import router as exams_router
from app.grammar.router import router as grammar_router
from app.mistakes.router import router as mistakes_router
from app.progress.router import router as progress_router
from app.review.router import router as review_router
from app.scanner.router import router as scanner_router
from app.sentences.router import router as sentences_router
from app.vocabulary.router import router as vocabulary_router

log = logging.getLogger(__name__)

DATABASE_DOWN = (
    "The database can't be reached right now. Please try again in a minute. If this goes on, "
    "the Supabase project may be paused: it needs restoring from the Supabase dashboard."
)


async def database_down_handler(_: Request, exc: Exception) -> JSONResponse:
    """A dropped connection, a paused Supabase project or a full pool: say so with a 503 the app
    retries, instead of an unexplained 500. Still reported, so an outage isn't silent."""
    log.error("Database unavailable: %s", type(exc).__name__)
    sentry_sdk.capture_exception(exc)
    return JSONResponse({"detail": DATABASE_DOWN}, status_code=503, headers={"Retry-After": "30"})


def sentry_options(dsn: str, environment: str) -> dict[str, Any]:
    """Error reports must carry a stack trace and nothing the learner wrote.

    Sentry's defaults would attach the parsed request body (up to 10 KB) and the local variables
    of every stack frame, whatever `send_default_pii` says. Those hold the learner's sentences and
    the class messages they paste, with other people's names. Both are switched off.
    """
    return {
        "dsn": dsn,
        "environment": environment,
        "traces_sample_rate": 0.0,  # errors only: stays inside the free plan
        "send_default_pii": False,
        "max_request_body_size": "never",
        "include_local_variables": False,
    }


def create_app() -> FastAPI:
    settings = get_settings()

    if settings.sentry_dsn:
        sentry_sdk.init(**sentry_options(settings.sentry_dsn, settings.environment))

    app = FastAPI(title="Lumen A1 Companion API", version="0.1.0")
    app.include_router(router)
    app.include_router(course_router)
    app.include_router(dictionary_router)
    app.include_router(vocabulary_router)
    app.include_router(review_router)
    app.include_router(grammar_router)
    app.include_router(mistakes_router)
    app.include_router(ai_router)
    app.include_router(coach_router)
    app.include_router(dashboard_router)
    app.include_router(exams_router)
    app.include_router(capture_router)
    app.include_router(scanner_router)
    app.include_router(community_router)
    app.include_router(sentences_router)
    app.include_router(progress_router)
    app.add_exception_handler(AiError, ai_error_handler)
    for database_error in (OperationalError, InterfaceError, PoolTimeoutError):
        app.add_exception_handler(database_error, database_down_handler)
    return app


app = create_app()
