from __future__ import annotations

import re
import secrets
from collections.abc import Mapping

from pydantic import SecretStr

_PRINCIPAL_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_MINIMUM_API_KEY_LENGTH = 32


class APIKeyAuthenticator:
    def __init__(self, api_keys: Mapping[str, str | SecretStr]) -> None:
        credentials: list[tuple[str, str]] = []
        seen_secrets: set[str] = set()
        for principal, secret in api_keys.items():
            value = secret.get_secret_value() if isinstance(secret, SecretStr) else secret
            if (
                _PRINCIPAL_PATTERN.fullmatch(principal) is None
                or value != value.strip()
                or not (_MINIMUM_API_KEY_LENGTH <= len(value) <= 512)
                or not value.isascii()
            ):
                raise ValueError("API key configuration is invalid")
            if value in seen_secrets:
                raise ValueError("API key values must be unique")
            seen_secrets.add(value)
            credentials.append((principal, value))

        self._credentials = tuple(credentials)

    def authenticate(self, candidate: str | None) -> str | None:
        safe_candidate = candidate if candidate is not None else ""
        if len(safe_candidate) > 512 or not safe_candidate.isascii():
            safe_candidate = ""

        matched_principal: str | None = None
        for principal, expected in self._credentials:
            if secrets.compare_digest(safe_candidate, expected):
                matched_principal = principal
        return matched_principal

    def __repr__(self) -> str:
        principals = tuple(principal for principal, _secret in self._credentials)
        return f"APIKeyAuthenticator(principals={principals!r})"
