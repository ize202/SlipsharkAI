# Local SSE demo

These files show the output of the repository's offline demo:

- `../screenshots/local-sse-stream.png` is a 1600 x 1400 terminal rendering.
- `local-sse-stream.mp4` is a silent 20-second H.264 recording that moves
  through the same transcript.

The source command was:

```bash
uv run python scripts/demo.py
```

It used the injected fixtures in `scripts/smoke.py`. No environment secrets,
provider accounts, Redis process, network request, or listening port were used.
The displayed request ID came from that run and is not a credential.

The recording is a readable presentation of captured command output, not a
screen recording of a live OpenAI or Exa request. Run the command again and
compare the event order when the contract changes: two `delta` events, one
`sources` event, then `done`.
