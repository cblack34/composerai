FROM ghcr.io/astral-sh/uv:0.12.23-python3.14-trixie-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
COPY packages/project-store/pyproject.toml packages/project-store/pyproject.toml
COPY packages/midi/pyproject.toml packages/midi/pyproject.toml
COPY apps/backend/pyproject.toml apps/backend/pyproject.toml

# music21's wheel bundles the core corpus. Those scores have their own copyrights.
# Drop them in this same RUN, before the layer is committed.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package composerai-backend --no-install-workspace \
    && find /app/.venv -path '*/music21/corpus/*' -type f ! -name '*.py' -delete \
    && find /app/.venv -depth -path '*/music21/corpus/*' -type d -empty -delete

COPY packages/project-store packages/project-store
COPY packages/midi packages/midi
COPY apps/backend apps/backend

# The second sync can re-extract the wheel. Prune again before this layer is committed.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package composerai-backend \
    && find /app/.venv -path '*/music21/corpus/*' -type f ! -name '*.py' -delete \
    && find /app/.venv -depth -path '*/music21/corpus/*' -type d -empty -delete

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []
CMD ["composerai-backend"]
