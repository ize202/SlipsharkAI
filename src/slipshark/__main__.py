from __future__ import annotations

import uvicorn

from slipshark.api.app import create_app
from slipshark.config import load_settings

app = create_app()


def main() -> None:
    global app
    settings = load_settings()
    app = create_app(settings=settings)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
