# Local SSE screenshot

`../screenshots/local-sse-stream.png` shows the output of the repository's
offline demo.

The source command was:

```bash
uv run python scripts/demo.py
```

It uses the fixtures in `scripts/smoke.py`, so it needs no keys or Redis
process. The expected event order is two `delta` events, one `sources` event,
then `done`.
