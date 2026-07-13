import json
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from slipshark.api.sse import encode_sse
from slipshark.domain.models import (
    DeltaEvent,
    DoneEvent,
    ErrorCode,
    ErrorEvent,
    PublicSource,
    SourcesEvent,
    StreamEvent,
)


def test_sse_encodes_one_json_data_line_and_one_terminator() -> None:
    request_id = uuid4()
    event = DeltaEvent(request_id=request_id, text="Café ⚽\nSecond line")

    encoded = encode_sse(event)
    lines = encoded.decode("utf-8").splitlines()

    assert encoded.startswith(b"event: delta\n")
    assert encoded.endswith(b"\n\n")
    assert not encoded.endswith(b"\n\n\n")
    assert len([line for line in lines if line.startswith("data: ")]) == 1

    payload = json.loads(lines[1].removeprefix("data: "))
    assert payload == {
        "request_id": str(request_id),
        "type": "delta",
        "text": "Café ⚽\nSecond line",
    }


def test_every_event_serializes_the_same_request_uuid() -> None:
    request_id = uuid4()
    source = PublicSource(id="nba", title="NBA", url="https://www.nba.com/")
    events: tuple[StreamEvent, ...] = (
        DeltaEvent(request_id=request_id, text="Answer"),
        SourcesEvent(request_id=request_id, sources=(source,)),
        DoneEvent(request_id=request_id),
        ErrorEvent(request_id=request_id, code=ErrorCode.PROVIDER_TIMEOUT),
    )

    for event in events:
        payload = json.loads(encode_sse(event).decode().splitlines()[1].removeprefix("data: "))
        assert UUID(payload["request_id"]) == request_id


def test_public_error_message_cannot_contain_exception_text() -> None:
    with pytest.raises(ValidationError):
        ErrorEvent(
            request_id=uuid4(),
            code=ErrorCode.INTERNAL_ERROR,
            message="socket reset by peer",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": str(uuid4())},
        {"type": "unknown", "request_id": str(uuid4())},
        {"type": "delta", "request_id": str(uuid4())},
        {"type": "sources", "request_id": str(uuid4())},
        {"type": "error", "request_id": str(uuid4()), "code": "raw_exception"},
        {"type": "done", "request_id": str(UUID(int=0))},
    ],
)
def test_invalid_event_variants_fail_validation(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(StreamEvent).validate_python(payload)
