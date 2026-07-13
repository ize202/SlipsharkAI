from __future__ import annotations

import os
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_VERIFY = _ROOT / "scripts" / "verify"


def test_fast_mode_owns_the_exact_checks_and_never_invokes_docker(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    invocation_log = tmp_path / "uv.log"
    uv = fake_bin / "uv"
    uv.write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >>"$VERIFY_LOG"\n')
    uv.chmod(0o755)
    docker = fake_bin / "docker"
    docker.write_text('#!/usr/bin/env bash\necho "docker called" >&2\nexit 99\n')
    docker.chmod(0o755)
    environment = dict(os.environ)
    environment.update(
        PATH=f"{fake_bin}:{environment['PATH']}",
        VERIFY_LOG=str(invocation_log),
    )

    result = subprocess.run(
        [_VERIFY],
        cwd=_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "docker called" not in result.stderr
    assert invocation_log.read_text().splitlines() == [
        "lock --check",
        "sync --frozen --all-groups",
        "run ruff format --check .",
        "run ruff check .",
        "run mypy src/slipshark",
        "run pytest -q",
        "run python scripts/smoke.py",
        "run python scripts/demo.py",
    ]


def test_verify_rejects_unknown_arguments_and_the_wrong_working_directory() -> None:
    unknown = subprocess.run(
        [_VERIFY, "--unknown"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    wrong_root = subprocess.run(
        [_VERIFY],
        cwd=_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert unknown.returncode == 2
    assert unknown.stderr == "Usage: ./scripts/verify [--full]\n"
    assert wrong_root.returncode == 2
    assert str(_ROOT) in wrong_root.stderr


def test_full_mode_is_isolated_bounded_and_ownership_aware() -> None:
    script = _VERIFY.read_text()

    assert "redis:8.8.0-alpine" in script
    assert "redis:latest" not in script
    assert "docker network create --internal" in script
    assert "--publish 127.0.0.1::8000/tcp" in script
    assert "redis_port_bindings" in script
    assert "for _attempt in {1..30}" in script
    assert "--connect-timeout 1 --max-time 2" in script
    assert "network_created=0" in script
    assert "redis_created=0" in script
    assert "app_created=0" in script
    assert "trap cleanup EXIT" in script
    assert "trap 'exit 129' HUP" in script
    assert "trap 'exit 130' INT" in script
    assert "trap 'exit 143' TERM" in script
    assert 'docker container rm --force "$app_name"' in script
    assert 'docker container rm --force "$redis_name"' in script
    assert 'docker network rm "$network_name"' in script
    assert '"$base_url/health/live"' in script
    assert '"$base_url/health/ready"' in script
    assert '"$base_url/research"' not in script
