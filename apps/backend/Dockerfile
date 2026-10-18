FROM ghcr.io/astral-sh/uv:0.12.23-python3.12-trixie-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
COPY packages/project-store/pyproject.toml packages/project-store/pyproject.toml
COPY apps/backend/pyproject.toml apps/backend/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package composerai-backend --no-install-workspace

COPY packages/project-store packages/project-store
COPY apps/backend apps/backend

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package composerai-backend

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []
CMD ["composerai-backend"]
