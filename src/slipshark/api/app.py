from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import SecretStr
from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from slipshark.api.dependencies import RuntimeServices, build_runtime_services
from slipshark.api.routes.health import router as health_router
from slipshark.api.routes.research import router as research_router
from slipshark.config import Settings, load_settings
from slipshark.providers.exa import ExaSearchProvider
from slipshark.providers.openai import OpenAIAnswerProvider, create_openai_client
from slipshark.providers.protocols import AnswerProvider, SearchProvider
from slipshark.security.rate_limit import RateLimiter, RedisRateLimiter


def create_app(
    settings: Settings | None = None,
    answer_provider: AnswerProvider | None = None,
    search_provider: SearchProvider | None = None,
    rate_limiter: RateLimiter | None = None,
) -> FastAPI:
    injected_count = sum(
        dependency is not None for dependency in (answer_provider, search_provider, rate_limiter)
    )
    if injected_count not in {0, 3}:
        raise ValueError(
            "answer provider, search provider, and rate limiter must be injected together"
        )
    if injected_count == 3 and settings is None:
        raise ValueError("injected runtime dependencies require explicit settings")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if (
            settings is not None
            and answer_provider is not None
            and search_provider is not None
            and rate_limiter is not None
        ):
            runtime = build_runtime_services(
                settings=settings,
                answer_provider=answer_provider,
                search_provider=search_provider,
                rate_limiter=rate_limiter,
            )
            application.state.runtime_services = runtime
            try:
                yield
            finally:
                del application.state.runtime_services
            return

        resolved_settings = settings if settings is not None else load_settings()
        async with _managed_runtime(resolved_settings) as runtime:
            application.state.runtime_services = runtime
            try:
                yield
            finally:
                del application.state.runtime_services

    application = FastAPI(
        title="Slipshark Research API",
        description="A bounded sports research service with structured streaming sources.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(health_router)
    application.include_router(research_router)
    return application


@asynccontextmanager
async def _managed_runtime(settings: Settings) -> AsyncIterator[RuntimeServices]:
    openai_key = _required_secret(settings.openai_api_key, name="OpenAI API key")
    exa_key = _required_secret(settings.exa_api_key, name="Exa API key")
    redis_url = _required_secret(settings.redis_url, name="Redis URL")
    if not settings.api_keys:
        raise RuntimeError("provider-backed runtime requires at least one API key principal")

    async with AsyncExitStack() as stack:
        openai_client = create_openai_client(api_key=openai_key)
        stack.push_async_callback(openai_client.close)
        http_client = await stack.enter_async_context(httpx.AsyncClient())
        redis_client = Redis.from_url(
            redis_url,
            decode_responses=True,
            retry=Retry(NoBackoff(), 0),
            retry_on_timeout=False,
            socket_connect_timeout=settings.redis_rate_limit_timeout_seconds,
            socket_timeout=settings.redis_rate_limit_timeout_seconds,
        )
        stack.push_async_callback(redis_client.aclose)

        runtime = build_runtime_services(
            settings=settings,
            answer_provider=OpenAIAnswerProvider(
                openai_client,
                planning_model=settings.openai_planning_model,
                answer_model=settings.openai_answer_model,
            ),
            search_provider=ExaSearchProvider(
                http_client,
                api_key=exa_key,
                max_text_chars=settings.per_source_char_limit,
                total_timeout_seconds=settings.exa_total_timeout_seconds,
                connect_timeout_seconds=settings.exa_connect_timeout_seconds,
            ),
            rate_limiter=RedisRateLimiter(
                redis_client,
                operation_timeout_seconds=settings.redis_rate_limit_timeout_seconds,
            ),
        )
        yield runtime


def _required_secret(value: SecretStr | None, *, name: str) -> str:
    if value is None:
        raise RuntimeError(f"provider-backed runtime requires {name}")
    return value.get_secret_value()


app = create_app()
