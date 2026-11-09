# Build stage: install dependencies with uv, which is not needed at runtime.
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Runtime stage: only the virtual environment and the application.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY app/ app/
COPY knowledge/ knowledge/

RUN useradd --system --no-create-home bot
USER bot

# Cloud Run already logs every request, so uvicorn's access log would only duplicate it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
