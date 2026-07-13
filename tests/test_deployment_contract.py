from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_is_pinned_non_root_and_uses_the_frozen_runtime() -> None:
    dockerfile = (_ROOT / "Dockerfile").read_text()

    assert dockerfile.startswith("FROM python:3.12.13-slim-bookworm\n")
    assert 'python -m pip install --no-cache-dir "uv==0.8.18"' in dockerfile
    assert "uv sync --frozen --no-dev --no-install-project" in dockerfile
    assert "uv sync --frozen --no-dev" in dockerfile
    assert dockerfile.index("COPY pyproject.toml uv.lock ./") < dockerfile.index("COPY src ./src")
    assert "COPY . " not in dockerfile
    assert "USER slipshark" in dockerfile
    assert "SLIPSHARK_HOST=0.0.0.0" in dockerfile
    assert "${PORT:-${SLIPSHARK_PORT:-8000}}" in dockerfile
    assert "exec env SLIPSHARK_PORT=" in dockerfile
    assert "python -m slipshark" in dockerfile

    for secret_name in (
        "SLIPSHARK_OPENAI_API_KEY",
        "SLIPSHARK_EXA_API_KEY",
        "SLIPSHARK_API_KEYS",
        "SLIPSHARK_REDIS_URL",
    ):
        assert secret_name not in dockerfile


def test_docker_context_is_an_explicit_source_allowlist() -> None:
    patterns = (_ROOT / ".dockerignore").read_text().splitlines()

    assert patterns == [
        "**",
        "!Dockerfile",
        "!.dockerignore",
        "!pyproject.toml",
        "!uv.lock",
        "!README.md",
        "!src/**/*.py",
    ]


def test_railway_uses_the_image_command_and_readiness_boundary() -> None:
    configuration = json.loads((_ROOT / "railway.json").read_text())

    assert configuration == {
        "$schema": "https://railway.com/railway.schema.json",
        "build": {
            "builder": "DOCKERFILE",
            "dockerfilePath": "Dockerfile",
        },
        "deploy": {
            "healthcheckPath": "/health/ready",
            "healthcheckTimeout": 30,
            "restartPolicyType": "ON_FAILURE",
            "restartPolicyMaxRetries": 5,
        },
    }
    assert not (_ROOT / "Procfile").exists()


def test_ci_delegates_to_the_full_repository_verifier() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    run_lines = [line.strip() for line in workflow.splitlines() if line.strip().startswith("run:")]

    assert run_lines == ["run: ./scripts/verify --full"]
    assert 'version: "0.8.18"' in workflow
