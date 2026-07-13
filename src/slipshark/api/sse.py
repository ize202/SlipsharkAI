from slipshark.domain.models import STREAM_EVENT_ADAPTER, StreamEvent


def encode_sse(event: StreamEvent) -> bytes:
    validated = STREAM_EVENT_ADAPTER.validate_python(event)
    payload = STREAM_EVENT_ADAPTER.dump_json(validated)
    return b"event: " + validated.type.encode("ascii") + b"\ndata: " + payload + b"\n\n"
