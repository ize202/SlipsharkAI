from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError
from redis.retry import Retry

from slipshark.api.app import create_app
from slipshark.api.dependencies import RuntimeServices
from slipshark.config import Environment, Settings


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeHTTPClient:
    def __init__(self) -> None:
        self.entered = False
        self.closed = False

    async def __aenter__(self) -> _FakeHTTPClient:
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.closed = True


class _FakeRedisClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def ping(self) -> bool:
        raise AssertionError("lifespan construction must not probe Redis")

    async def eval(self, script: str, numkeys: int, *args: object) -> object:
        raise AssertionError("lifespan construction must not consume rate limit state")


@pytest.mark.asyncio
async def test_managed_lifespan_constructs_and_closes_owned_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module = importlib.import_module("slipshark.api.app")
    openai_client = _FakeOpenAIClient()
    http_client = _FakeHTTPClient()
    redis_client = _FakeRedisClient()
    redis_arguments: dict[str, object] = {}

    monkeypatch.setattr(app_module, "create_openai_client", lambda **_kwargs: openai_client)
    monkeypatch.setattr(app_module.httpx, "AsyncClient", lambda: http_client)

    def redis_from_url(
        _cls: object,
        url: str,
        **kwargs: object,
    ) -> _FakeRedisClient:
        redis_arguments.update(url=url, **kwargs)
        return redis_client

    monkeypatch.setattr(app_module.Redis, "from_url", classmethod(redis_from_url))
    settings = Settings(
        environment=Environment.PRODUCTION,
        openai_api_key="openai-production-placeholder",
        exa_api_key="exa-production-placeholder",
        api_keys={"ios-client": "sk_v1_productionplaceholderabcdefgh123456"},
        redis_url="rediss://redis.example.invalid:6380/0",
        redis_rate_limit_timeout_seconds=1.5,
        _env_file=None,
    )
    application = create_app(settings=settings)

    async with application.router.lifespan_context(application):
        runtime = application.state.runtime_services
        assert isinstance(runtime, RuntimeServices)
        assert runtime.settings is settings
        assert openai_client.closed is False
        assert http_client.entered is True
        assert http_client.closed is False
        assert redis_client.closed is False

    assert openai_client.closed is True
    assert http_client.closed is True
    assert redis_client.closed is True
    assert redis_arguments["url"] == "rediss://redis.example.invalid:6380/0"
    assert redis_arguments["decode_responses"] is True
    assert redis_arguments["retry_on_timeout"] is False
    assert redis_arguments["socket_connect_timeout"] == 1.5
    assert redis_arguments["socket_timeout"] == 1.5
    retry = redis_arguments["retry"]
    assert isinstance(retry, Retry)
    assert retry.get_retries() == 0


def test_partial_runtime_injection_is_rejected() -> None:
    settings = Settings(environment=Environment.TEST, _env_file=None)

    with pytest.raises(ValueError, match="must be injected together"):
        create_app(settings=settings, answer_provider=object())


def test_settings_reject_per_source_limit_the_managed_adapter_cannot_accept() -> None:
    with pytest.raises(ValidationError, match="per_source_char_limit"):
        Settings(
            environment=Environment.TEST,
            per_source_char_limit=4_001,
            _env_file=None,
        )
