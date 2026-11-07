# Haven backend

API, engines and data access for Haven. Managed with [uv](https://docs.astral.sh/uv/); tasks run through poethepoet.

```
uv run --directory backend poe lint    # ruff check, ruff format --check, mypy
uv run --directory backend poe test    # pytest
uv run --directory backend poe fmt     # format + safe lint fixes
uv run --directory backend poe serve   # uvicorn on http://localhost:8000 (reload)
```
