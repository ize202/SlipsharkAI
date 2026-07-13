from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from slipshark.api.dependencies import build_runtime_services
from slipshark.config import Environment, Settings
from slipshark.domain.models import Platform, ResearchQuery, SearchDecision, SourceDocument
from slipshark.security.rate_limit import InMemoryRateLimiter

_PRODUCTION_VARIABLES = (
    "SLIPSHARK_ENVIRONMENT",
    "SLIPSHARK_OPENAI_API_KEY",
    "SLIPSHARK_EXA_API_KEY",
    "SLIPSHARK_API_KEYS",
    "SLIPSHARK_REDIS_URL",
)


def _clear_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _PRODUCTION_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_importing_config_does_not_validate_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_environment(monkeypatch)

    module = importlib.import_module("slipshark.config")

    assert module.Settings is Settings


def test_environment_is_required_when_settings_are_constructed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_environment(monkeypatch)

    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)

    assert "environment" in str(caught.value)


def test_production_requires_every_secret_and_redis_value() -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(environment=Environment.PRODUCTION, _env_file=None)

    error = str(caught.value)
    assert "openai_api_key" in error
    assert "exa_api_key" in error
    assert "api_keys" in error
    assert "redis_url" in error


def test_slipshark_prefixed_environment_builds_frozen_production_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("SLIPSHARK_ENVIRONMENT", "production")
    monkeypatch.setenv("SLIPSHARK_OPENAI_API_KEY", "openai-test-value")
    monkeypatch.setenv("SLIPSHARK_EXA_API_KEY", "exa-test-value")
    monkeypatch.setenv(
        "SLIPSHARK_API_KEYS",
        '{"ios-client":"sk_v1_abcdefghijklmnopqrstuvwxyz123456"}',
    )
    monkeypatch.setenv("SLIPSHARK_REDIS_URL", "redis://localhost:6379/0")

    settings = Settings(_env_file=None)

    assert settings.environment is Environment.PRODUCTION
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "openai-test-value"
    assert settings.exa_api_key is not None
    assert settings.exa_api_key.get_secret_value() == "exa-test-value"
    assert settings.api_keys["ios-client"].get_secret_value().startswith("sk_v1_")
    assert settings.redis_url is not None
    assert settings.redis_url.get_secret_value() == "redis://localhost:6379/0"
    assert "openai-test-value" not in repr(settings)
    assert "redis://localhost:6379/0" not in repr(settings)

    with pytest.raises(ValidationError):
        settings.environment = Environment.TEST

    with pytest.raises(TypeError):
        settings.api_keys["new-client"] = SecretStr("sk_v1_anotherlongrandomserverkey123456")


def test_api_keys_reject_short_or_duplicate_secrets_without_echoing_them() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment=Environment.LOCAL,
            api_keys={"ios-client": "too-short"},
            _env_file=None,
        )

    duplicate = "sk_v1_duplicatevalueabcdefghijklmnop123456"
    with pytest.raises(ValidationError) as caught:
        Settings(
            environment=Environment.LOCAL,
            api_keys={"ios-client": duplicate, "automation": duplicate},
            _env_file=None,
        )

    assert duplicate not in str(caught.value)


def test_constructor_rejects_unknown_settings_instead_of_ignoring_typos() -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(environment=Environment.LOCAL, typo_value="ignored", _env_file=None)

    assert "typo_value" in str(caught.value)


class _FakeAnswerProvider:
    async def decide_search(
        self,
        query: ResearchQuery,
        *,
        now: datetime,
    ) -> SearchDecision:
        return SearchDecision(requires_search=False)

    def stream_answer(
        self,
        query: ResearchQuery,
        *,
        sources: Sequence[SourceDocument],
        now: datetime,
    ) -> AsyncIterator[str]:
        async def stream() -> AsyncIterator[str]:
            yield "Injected local answer."

        return stream()


class _FailIfCalledSearchProvider:
    async def search(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]:
        raise AssertionError("no-search injection path must not call search")


@pytest.mark.parametrize("environment", [Environment.LOCAL, Environment.TEST])
@pytest.mark.asyncio
async def test_local_and_test_settings_build_a_real_injected_runtime_without_secrets(
    environment: Environment,
) -> None:
    settings = Settings(environment=environment, _env_file=None)
    limiter = InMemoryRateLimiter()

    runtime = build_runtime_services(
        settings=settings,
        answer_provider=_FakeAnswerProvider(),
        search_provider=_FailIfCalledSearchProvider(),
        rate_limiter=limiter,
    )
    events = [
        event
        async for event in runtime.research_service.stream(
            ResearchQuery(query="local test", platform=Platform.WEB, max_results=3),
            uuid4(),
        )
    ]

    assert settings.openai_api_key is None
    assert settings.exa_api_key is None
    assert settings.api_keys == {}
    assert settings.redis_url is None
    assert runtime.settings is settings
    assert runtime.rate_limiter is limiter
    assert runtime.authenticator.authenticate(None) is None
    assert [event.type for event in events] == ["delta", "sources", "done"]


def test_production_runtime_rejects_the_process_local_limiter() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION,
        openai_api_key="openai-production-placeholder",
        exa_api_key="exa-production-placeholder",
        api_keys={"ios-client": "sk_v1_productionplaceholderabcdefgh123456"},
        redis_url="rediss://redis.example.invalid:6380/0",
        _env_file=None,
    )

    with pytest.raises(ValueError, match="shared rate limiter"):
        build_runtime_services(
            settings=settings,
            answer_provider=_FakeAnswerProvider(),
            search_provider=_FailIfCalledSearchProvider(),
            rate_limiter=InMemoryRateLimiter(),
        )
