from __future__ import annotations

import json
import string
import subprocess
import sys
from pathlib import Path

_GENERATE_KEY_SCRIPT = Path(__file__).resolve().parents[1] / "generate_key.py"


def _generate_key() -> str:
    result = subprocess.run(
        [sys.executable, str(_GENERATE_KEY_SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
    )
    assignment = result.stdout.splitlines()[-1]
    name, raw_mapping = assignment.split("=", maxsplit=1)
    assert name == "SLIPSHARK_API_KEYS"
    mapping = json.loads(raw_mapping)
    assert set(mapping) == {"local-cli"}
    return mapping["local-cli"]


def test_generated_api_key_is_long_ascii_and_url_safe() -> None:
    key = _generate_key()

    assert key.startswith("sk_v1_")
    assert len(key) >= 32
    assert key.isascii()
    assert set(key) <= set(string.ascii_letters + string.digits + "_-")


def test_generated_api_keys_are_unique() -> None:
    assert _generate_key() != _generate_key()
