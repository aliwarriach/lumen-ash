"""FastAPI wiring for the AI layer. Tests replace `get_providers` with fakes."""

from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from app.ai.budget import Limits
from app.ai.gateway import AiGateway, Cooldowns
from app.ai.providers import AiProvider, build_providers
from app.core.config import get_settings
from app.core.database import SessionDep


@lru_cache
def get_providers() -> tuple[AiProvider, ...]:
    # One shared HTTP client for the life of the process.
    return tuple(build_providers(get_settings(), httpx.AsyncClient()))


@lru_cache
def get_limits() -> Limits:
    return Limits.from_settings(get_settings())


@lru_cache
def get_cooldowns() -> Cooldowns:
    return Cooldowns()


ProvidersDep = Annotated[tuple[AiProvider, ...], Depends(get_providers)]
LimitsDep = Annotated[Limits, Depends(get_limits)]


def get_gateway(
    session: SessionDep,
    providers: ProvidersDep,
    limits: LimitsDep,
    cooldowns: Annotated[Cooldowns, Depends(get_cooldowns)],
) -> AiGateway:
    return AiGateway(
        session, providers, limits, cooldowns, redact_names=get_settings().redact_names
    )


GatewayDep = Annotated[AiGateway, Depends(get_gateway)]
