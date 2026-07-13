FROM python:3.12.13-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    SLIPSHARK_HOST=0.0.0.0 \
    SLIPSHARK_PORT=8000

WORKDIR /app

RUN python -m pip install --no-cache-dir "uv==0.8.18"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

RUN groupadd --system --gid 10001 slipshark \
    && useradd --system --uid 10001 --gid 10001 --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin --no-log-init slipshark

USER slipshark

EXPOSE 8000

CMD ["sh", "-c", "exec env SLIPSHARK_PORT=\"${PORT:-${SLIPSHARK_PORT:-8000}}\" python -m slipshark"]
