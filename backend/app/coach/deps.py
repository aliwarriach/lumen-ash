"""FastAPI wiring for the sentence coach. Tests replace `get_languagetool` with a fake."""

from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from app.coach.languagetool import LanguageToolClient
from app.core.config import get_settings


@lru_cache
def get_languagetool() -> LanguageToolClient | None:
    settings = get_settings()
    if not settings.languagetool_url:
        return None
    return LanguageToolClient(
        httpx.AsyncClient(),
        settings.languagetool_url,
        settings.languagetool_timeout_seconds,
        settings.languagetool_per_minute,
    )


LanguageToolDep = Annotated[LanguageToolClient | None, Depends(get_languagetool)]
