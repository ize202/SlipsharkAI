from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, StringConstraints, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PRINCIPAL_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,63}")


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SLIPSHARK_",
        env_file=None,
        dotenv_filtering="match_prefix",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    environment: Environment
    openai_api_key: SecretStr | None = None
    exa_api_key: SecretStr | None = None
    api_keys: Mapping[str, SecretStr] = Field(default_factory=dict)
    redis_url: SecretStr | None = None
    host: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ] = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65_535)

    max_query_chars: int = Field(default=1_000, ge=1, le=1_000)
    max_results: int = Field(default=10, ge=1, le=10)
    planner_timeout_seconds: float = Field(default=10, gt=0, le=60)
    search_timeout_seconds: float = Field(default=10, gt=0, le=60)
    answer_timeout_seconds: float = Field(default=30, gt=0, le=120)
    request_timeout_seconds: float = Field(default=45, gt=0, le=180)
    per_source_char_limit: int = Field(default=4_000, ge=1, le=4_000)
    total_source_char_limit: int = Field(default=16_000, ge=1, le=64_000)
    answer_char_limit: int = Field(default=12_000, ge=1, le=48_000)
    exa_connect_timeout_seconds: float = Field(default=3, gt=0, le=30)
    exa_total_timeout_seconds: float = Field(default=10, gt=0, le=60)
    openai_planning_model: str = "gpt-4o-mini"
    openai_answer_model: str = "gpt-4o"
    rate_limit_requests: int = Field(default=10, ge=1, le=10_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=86_400)
    redis_rate_limit_timeout_seconds: float = Field(default=2, gt=0, le=10)

    @field_validator("openai_api_key", "exa_api_key")
    @classmethod
    def _validate_optional_provider_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        cls._validate_secret(value, field_name="provider API key")
        return value

    @field_validator("redis_url")
    @classmethod
    def _validate_optional_redis_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        raw_url = cls._validate_secret(value, field_name="Redis URL")
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"redis", "rediss"} or parsed.hostname is None:
            raise ValueError("redis_url must be a redis:// or rediss:// URL with a host")
        return value

    @field_validator("api_keys")
    @classmethod
    def _validate_and_freeze_api_keys(
        cls,
        value: Mapping[str, SecretStr],
    ) -> Mapping[str, SecretStr]:
        normalized: dict[str, SecretStr] = {}
        seen_secrets: set[str] = set()
        for principal, secret in value.items():
            if _PRINCIPAL_PATTERN.fullmatch(principal) is None:
                raise ValueError(
                    "api_keys principal IDs must use lowercase letters, digits, hyphens, or underscores"
                )
            raw_secret = cls._validate_secret(
                secret,
                field_name="API key",
                minimum_length=32,
            )
            if raw_secret in seen_secrets:
                raise ValueError("api_keys values must be unique")
            seen_secrets.add(raw_secret)
            normalized[principal] = secret
        return MappingProxyType(normalized)

    @model_validator(mode="after")
    def _validate_settings(self) -> Settings:
        if self.per_source_char_limit > self.total_source_char_limit:
            raise ValueError("per_source_char_limit cannot exceed total_source_char_limit")
        if self.exa_connect_timeout_seconds > self.exa_total_timeout_seconds:
            raise ValueError("exa_connect_timeout_seconds cannot exceed exa_total_timeout_seconds")

        if self.environment is not Environment.PRODUCTION:
            return self

        missing: list[str] = []
        if self.openai_api_key is None:
            missing.append("openai_api_key")
        if self.exa_api_key is None:
            missing.append("exa_api_key")
        if not self.api_keys:
            missing.append("api_keys")
        if self.redis_url is None:
            missing.append("redis_url")
        if missing:
            raise ValueError(f"production settings require: {', '.join(missing)}")
        return self

    @staticmethod
    def _validate_secret(
        secret: SecretStr,
        *,
        field_name: str,
        minimum_length: int = 1,
    ) -> str:
        value = secret.get_secret_value()
        if not value or value != value.strip():
            raise ValueError(f"{field_name} must not be blank or contain surrounding whitespace")
        if len(value) < minimum_length:
            raise ValueError(f"{field_name} must contain at least {minimum_length} characters")
        if len(value) > 512:
            raise ValueError(f"{field_name} must not exceed 512 characters")
        if not value.isascii():
            raise ValueError(f"{field_name} must contain only ASCII characters")
        return value


def load_settings() -> Settings:
    # BaseSettings supplies required fields from the environment at runtime;
    # mypy cannot model that alternate construction path.
    return Settings()  # type: ignore[call-arg]
