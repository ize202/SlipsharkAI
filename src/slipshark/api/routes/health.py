from __future__ import annotations

import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from slipshark.api.dependencies import get_runtime_services
from slipshark.security.rate_limit import InMemoryRateLimiter

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> JSONResponse:
    runtime = get_runtime_services(request)
    if isinstance(runtime.rate_limiter, InMemoryRateLimiter):
        return JSONResponse(
            {
                "status": "ready",
                "configuration": "ready",
                "redis": "not_required",
            }
        )

    try:
        redis_ready = await runtime.rate_limiter.ready()
    except Exception:
        logger.exception("Rate-limiter readiness probe failed")
        redis_ready = False

    if redis_ready:
        return JSONResponse(
            {
                "status": "ready",
                "configuration": "ready",
                "redis": "ready",
            }
        )

    return JSONResponse(
        {
            "status": "not_ready",
            "configuration": "ready",
            "redis": "unavailable",
        },
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
