from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from slipshark.config import Environment, Settings
from slipshark.providers.protocols import AnswerProvider, SearchProvider
from slipshark.security.auth import APIKeyAuthenticator
from slipshark.security.rate_limit import (
    InMemoryRateLimiter,
    RateLimitDecision,
    RateLimiter,
    RateLimitUnavailableError,
)
from slipshark.services.research import ResearchLimits, ResearchService

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyDependency:
    def __init__(self, authenticator: APIKeyAuthenticator | None = None) -> None:
        self._authenticator = authenticator

    def __call__(
        self,
        request: Request,
        candidate: Annotated[str | None, Security(API_KEY_HEADER)],
    ) -> str:
        authenticator = self._authenticator
        if authenticator is None:
            authenticator = get_runtime_services(request).authenticator
        return authenticate_api_key(candidate, authenticator=authenticator)


@dataclass(frozen=True, slots=True)
class RuntimeServices:
    settings: Settings
    authenticator: APIKeyAuthenticator
    research_service: ResearchService
    rate_limiter: RateLimiter


def get_runtime_services(request: Request) -> RuntimeServices:
    runtime = getattr(request.app.state, "runtime_services", None)
    if not isinstance(runtime, RuntimeServices):
        raise RuntimeError("application runtime is unavailable")
    return runtime


def build_runtime_services(
    *,
    settings: Settings,
    answer_provider: AnswerProvider,
    search_provider: SearchProvider,
    rate_limiter: RateLimiter,
) -> RuntimeServices:
    if settings.environment is Environment.PRODUCTION and isinstance(
        rate_limiter, InMemoryRateLimiter
    ):
        raise ValueError("production requires a shared rate limiter")

    limits = ResearchLimits(
        planner_timeout_seconds=settings.planner_timeout_seconds,
        search_timeout_seconds=settings.search_timeout_seconds,
        answer_timeout_seconds=settings.answer_timeout_seconds,
        request_timeout_seconds=settings.request_timeout_seconds,
        per_source_char_limit=settings.per_source_char_limit,
        total_source_char_limit=settings.total_source_char_limit,
        answer_char_limit=settings.answer_char_limit,
    )
    return RuntimeServices(
        settings=settings,
        authenticator=APIKeyAuthenticator(settings.api_keys),
        research_service=ResearchService(
            search_provider,
            answer_provider,
            limits=limits,
        ),
        rate_limiter=rate_limiter,
    )


def authenticate_api_key(
    candidate: str | None,
    *,
    authenticator: APIKeyAuthenticator,
) -> str:
    principal = authenticator.authenticate(candidate)
    if principal is None:
        raise API_KEY_HEADER.make_not_authenticated_error()
    return principal


async def enforce_rate_limit(
    subject: str,
    *,
    limiter: RateLimiter,
    limit: int = 10,
    window_seconds: int = 60,
) -> RateLimitDecision:
    try:
        decision = await limiter.consume(
            subject,
            limit=limit,
            window_seconds=window_seconds,
        )
    except RateLimitUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting is temporarily unavailable.",
        ) from error

    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
    return decision
