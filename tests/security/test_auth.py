import logging
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.exceptions import HTTPException

from slipshark.api.dependencies import APIKeyDependency, authenticate_api_key
from slipshark.security.auth import APIKeyAuthenticator

_VALID_KEY = "sk_v1_abcdefghijklmnopqrstuvwxyz123456"
_SECOND_KEY = "sk_v1_654321zyxwvutsrqponmlkjihgfedcba"


def _http_failure(candidate: str | None, authenticator: APIKeyAuthenticator) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        authenticate_api_key(candidate, authenticator=authenticator)
    return caught.value


def test_missing_malformed_and_unknown_keys_have_one_public_401_shape() -> None:
    authenticator = APIKeyAuthenticator({"ios-client": _VALID_KEY})

    failures = [
        _http_failure(None, authenticator),
        _http_failure(" ", authenticator),
        _http_failure("not-an-api-key", authenticator),
        _http_failure("not-ascii-\u2603", authenticator),
        _http_failure("x" * 513, authenticator),
        _http_failure("sk_v1_00000000000000000000000000000000", authenticator),
    ]

    shapes = {
        (failure.status_code, str(failure.detail), tuple(sorted(failure.headers.items())))
        for failure in failures
    }
    assert len(shapes) == 1
    [failure] = failures[:1]
    assert failure.status_code == 401
    assert failure.headers == {"WWW-Authenticate": "APIKey"}
    assert _VALID_KEY not in str(failure.detail)


def test_authenticator_returns_only_the_stable_principal() -> None:
    authenticator = APIKeyAuthenticator({"ios-client": _VALID_KEY, "automation": _SECOND_KEY})

    principal = authenticate_api_key(_SECOND_KEY, authenticator=authenticator)

    assert principal == "automation"
    assert _SECOND_KEY not in principal


def test_every_configured_secret_uses_compare_digest_even_after_a_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def compare_digest(left: str, right: str) -> bool:
        calls.append((left, right))
        return left == right

    monkeypatch.setattr("slipshark.security.auth.secrets.compare_digest", compare_digest)
    authenticator = APIKeyAuthenticator({"ios-client": _VALID_KEY, "automation": _SECOND_KEY})

    assert authenticate_api_key(_VALID_KEY, authenticator=authenticator) == "ios-client"
    assert len(calls) == 2
    assert all(_VALID_KEY in call for call in calls)
    assert {_VALID_KEY, _SECOND_KEY} == {
        next(value for value in call if value != _VALID_KEY) if call[0] != call[1] else _VALID_KEY
        for call in calls
    }


def test_candidate_key_is_not_logged_or_retained(
    caplog: pytest.LogCaptureFixture,
) -> None:
    candidate = "sk_v1_privatecandidate000000000000000"
    authenticator = APIKeyAuthenticator({"ios-client": _VALID_KEY})

    with caplog.at_level(logging.DEBUG):
        _http_failure(candidate, authenticator)

    assert candidate not in caplog.text
    assert candidate not in repr(authenticator)
    retained_state = getattr(authenticator, "__dict__", {})
    assert all(candidate not in repr(value) for value in retained_state.values())


@pytest.mark.parametrize(
    "credentials",
    [
        {"Invalid Principal": _VALID_KEY},
        {"ios-client": "too-short"},
    ],
)
def test_authenticator_rejects_unsafe_configuration(credentials: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="configuration is invalid"):
        APIKeyAuthenticator(credentials)


def _protected_app(authenticator: APIKeyAuthenticator) -> FastAPI:
    app = FastAPI()
    principal_dependency = APIKeyDependency(authenticator)

    @app.get("/protected")
    async def protected(
        principal: Annotated[str, Depends(principal_dependency)],
    ) -> dict[str, str]:
        return {"principal": principal}

    return app


@pytest.mark.asyncio
async def test_fastapi_boundary_extracts_x_api_key_with_one_failure_shape() -> None:
    app = _protected_app(APIKeyAuthenticator({"ios-client": _VALID_KEY}))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.get("/protected")
        unknown = await client.get("/protected", headers={"X-API-Key": "x" * 32})
        valid = await client.get("/protected", headers={"X-API-Key": _VALID_KEY})

    assert missing.status_code == unknown.status_code == 401
    assert missing.json() == unknown.json() == {"detail": "Not authenticated"}
    assert missing.headers["www-authenticate"] == "APIKey"
    assert unknown.headers["www-authenticate"] == "APIKey"
    assert valid.status_code == 200
    assert valid.json() == {"principal": "ios-client"}


def test_fastapi_boundary_declares_the_header_security_scheme() -> None:
    app = _protected_app(APIKeyAuthenticator({"ios-client": _VALID_KEY}))

    schema = app.openapi()

    assert schema["components"]["securitySchemes"]["APIKeyHeader"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    assert schema["paths"]["/protected"]["get"]["security"] == [{"APIKeyHeader": []}]
