from __future__ import annotations

import asyncio
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _load_smoke_module() -> ModuleType:
    path = _REPOSITORY_ROOT / "scripts" / "smoke.py"
    spec = importlib.util.spec_from_file_location("slipshark_offline_smoke", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load_smoke_module()


def _run_script(path: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.update(
        {
            "SLIPSHARK_ENVIRONMENT": "production",
            "SLIPSHARK_API_KEYS": "not-json",
            "SLIPSHARK_OPENAI_API_KEY": "must-not-be-read",
            "SLIPSHARK_EXA_API_KEY": "must-not-be-read",
            "SLIPSHARK_REDIS_URL": "not-a-redis-url",
        }
    )
    return subprocess.run(
        [sys.executable, path],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_smoke_script_passes_with_poisoned_provider_environment() -> None:
    result = _run_script("scripts/smoke.py")

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        "PASS GET /health/live",
        "PASS GET /health/ready",
        "PASS POST /research (delta, delta, sources, done)",
        "Slipshark offline smoke passed",
    ]


def test_demo_script_prints_one_complete_valid_transcript() -> None:
    result = _run_script("scripts/demo.py")

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.startswith("LOCAL SIMULATION —")
    transcript_start = result.stdout.index("event: ")
    events = smoke.validate_sse_transcript(result.stdout[transcript_start:].encode())
    smoke.validate_expected_research(events)
    assert tuple(event.type for event in events) == ("delta", "delta", "sources", "done")


def test_smoke_main_returns_nonzero_when_validation_fails(
    monkeypatch,
    capsys,
) -> None:
    async def fail() -> None:
        raise smoke.SmokeFailure("fixture mismatch")

    monkeypatch.setattr(smoke, "run_smoke", fail)

    assert smoke.main() == 1
    assert capsys.readouterr().err == "Slipshark offline smoke failed: fixture mismatch\n"


def test_offline_app_ignores_environment_and_uses_injected_runtime(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SLIPSHARK_API_KEYS", "not-json")
    monkeypatch.setenv("SLIPSHARK_OPENAI_API_KEY", "must-not-be-read")
    monkeypatch.setenv("SLIPSHARK_REDIS_URL", "not-a-redis-url")

    asyncio.run(smoke.run_smoke())
