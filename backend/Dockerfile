# Haven API image. Build context: backend/ (see docker-compose.yml at the repo root).
# Note: the API reads contract examples and reference data from the repo root, so compose
# mounts ../contracts and ../data into /repo; the package itself lives in /repo/backend.
FROM python:3.12-slim

COPY --from=astral/uv:0.13.7 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /repo/backend

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY haven ./haven
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 1000 haven
USER haven

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["/repo/backend/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["/repo/backend/.venv/bin/uvicorn", "haven.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
