from __future__ import annotations

import ast
import importlib
import os
import runpy
import sys
from pathlib import Path
from typing import Any

import httpx
import openai
import pytest
import redis.asyncio as redis_asyncio
import uvicorn
from pydantic import ValidationError

import slipshark.api as api_package
import slipshark.config as config_module
import slipshark.providers.openai as openai_provider_module
from slipshark.config import Environment, Settings

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


def _clear_slipshark_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.startswith("SLIPSHARK_"):
            monkeypatch.delenv(name, raising=False)


def _fail_if_constructed(*args: object, **kwargs: object) -> Any:
    del args, kwargs
    raise AssertionError("root application import must not construct runtime clients or settings")


def test_root_main_is_an_import_only_lazy_compatibility_shim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_slipshark_environment(monkeypatch)

    parsed = ast.parse((_REPOSITORY_ROOT / "main.py").read_text())
    assert len(parsed.body) == 1
    statement = parsed.body[0]
    assert isinstance(statement, ast.ImportFrom)
    assert statement.module == "slipshark.api.app"
    assert [(alias.name, alias.asname) for alias in statement.names] == [("app", None)]

    monkeypatch.setattr(config_module.Settings, "__init__", _fail_if_constructed)
    monkeypatch.setattr(openai_provider_module, "create_openai_client", _fail_if_constructed)
    monkeypatch.setattr(openai_provider_module, "AsyncOpenAI", _fail_if_constructed)
    monkeypatch.setattr(openai, "AsyncOpenAI", _fail_if_constructed)
    monkeypatch.setattr(httpx, "AsyncClient", _fail_if_constructed)
    monkeypatch.setattr(redis_asyncio, "from_url", _fail_if_constructed)
    monkeypatch.setattr(
        redis_asyncio.Redis,
        "from_url",
        classmethod(_fail_if_constructed),
    )

    module_names = ("main", "slipshark.api.app")
    previous_modules = {name: sys.modules.get(name, _MISSING) for name in module_names}
    previous_package_app = api_package.__dict__.get("app", _MISSING)
    monkeypatch.syspath_prepend(str(_REPOSITORY_ROOT))
    for name in module_names:
        sys.modules.pop(name, None)
    api_package.__dict__.pop("app", None)

    try:
        compatibility_module = importlib.import_module("main")
        application_module = sys.modules["slipshark.api.app"]
        assert compatibility_module.app is application_module.app
    finally:
        for name, previous in previous_modules.items():
            sys.modules.pop(name, None)
            if previous is not _MISSING:
                sys.modules[name] = previous
        api_package.__dict__.pop("app", None)
        if previous_package_app is not _MISSING:
            api_package.__dict__["app"] = previous_package_app


def test_python_m_slipshark_uses_prefixed_host_and_port_without_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_slipshark_environment(monkeypatch)
    monkeypatch.setenv("SLIPSHARK_ENVIRONMENT", "local")
    monkeypatch.setenv("SLIPSHARK_HOST", "127.0.0.7")
    monkeypatch.setenv("SLIPSHARK_PORT", "8765")

    observed: dict[str, object] = {}

    def fake_run(application: object, **kwargs: object) -> None:
        observed.update(app=application, **kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    namespace = runpy.run_module("slipshark.__main__", run_name="__main__")

    assert observed["app"] is namespace["app"]
    assert observed["host"] == "127.0.0.7"
    assert observed["port"] == 8765


def test_server_bind_settings_accept_valid_values_and_reject_invalid_ports() -> None:
    settings = Settings(
        environment=Environment.LOCAL,
        host="127.0.0.7",
        port=65_535,
        _env_file=None,
    )

    assert settings.host == "127.0.0.7"
    assert settings.port == 65_535

    for invalid_port in (0, 65_536):
        with pytest.raises(ValidationError):
            Settings(
                environment=Environment.LOCAL,
                host="127.0.0.7",
                port=invalid_port,
                _env_file=None,
            )
