from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.smoke import FIXED_QUERY, collect_research_transcript  # noqa: E402

_LABEL = "LOCAL SIMULATION: deterministic fixtures; no network or provider calls"


async def run_demo() -> None:
    transcript = await collect_research_transcript()
    print(_LABEL)
    print(f"Query: {FIXED_QUERY}")
    print()
    sys.stdout.write(transcript.decode("utf-8"))


def main() -> int:
    try:
        asyncio.run(run_demo())
    except Exception as error:
        print(f"LOCAL SIMULATION failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
