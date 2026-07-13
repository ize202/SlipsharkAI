import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from slipshark.api.dependencies import (
    APIKeyDependency,
    enforce_rate_limit,
    get_runtime_services,
)
from slipshark.api.models import ResearchRequest
from slipshark.api.sse import encode_sse
from slipshark.domain.models import ErrorCode, ErrorEvent, ResearchQuery
from slipshark.services.research import ResearchTimeoutError, ResearchUnavailableError

router = APIRouter(tags=["research"])
logger = logging.getLogger(__name__)
_authenticated_principal = APIKeyDependency()


@router.post("/research", response_class=StreamingResponse)
async def research(
    request: Request,
    body: ResearchRequest,
    principal: Annotated[str, Depends(_authenticated_principal)],
) -> StreamingResponse:
    runtime = get_runtime_services(request)
    if (
        len(body.query) > runtime.settings.max_query_chars
        or body.max_results > runtime.settings.max_results
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Research request exceeds the configured limits.",
        )

    await enforce_rate_limit(
        principal,
        limiter=runtime.rate_limiter,
        limit=runtime.settings.rate_limit_requests,
        window_seconds=runtime.settings.rate_limit_window_seconds,
    )

    request_id = uuid4()
    query = ResearchQuery(
        query=body.query,
        platform=body.platform,
        max_results=body.max_results,
    )
    return StreamingResponse(
        _stream_events(request, query=query, request_id=request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_events(
    request: Request,
    *,
    query: ResearchQuery,
    request_id: UUID,
) -> AsyncIterator[bytes]:
    runtime = get_runtime_services(request)
    try:
        async with aclosing(runtime.research_service.stream(query, request_id)) as events:
            async for event in events:
                yield encode_sse(event)
    except ResearchTimeoutError:
        logger.exception(
            "Research stream failed",
            extra={"request_id": str(request_id), "error_code": ErrorCode.PROVIDER_TIMEOUT},
        )
        yield encode_sse(ErrorEvent(request_id=request_id, code=ErrorCode.PROVIDER_TIMEOUT))
    except ResearchUnavailableError:
        logger.exception(
            "Research stream failed",
            extra={
                "request_id": str(request_id),
                "error_code": ErrorCode.PROVIDER_UNAVAILABLE,
            },
        )
        yield encode_sse(ErrorEvent(request_id=request_id, code=ErrorCode.PROVIDER_UNAVAILABLE))
    except Exception:
        logger.exception(
            "Research stream failed",
            extra={"request_id": str(request_id), "error_code": ErrorCode.INTERNAL_ERROR},
        )
        yield encode_sse(ErrorEvent(request_id=request_id, code=ErrorCode.INTERNAL_ERROR))
