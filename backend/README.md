# PARALLAX — backend

FastAPI service, SQLAlchemy models, and Alembic migrations for PARALLAX.
Project overview, architecture, and the Docker quick start live in the
[root README](../README.md).

```
src/parallax/
  main.py          app factory + ASGI entrypoint
  core/            settings, logging, domain exceptions
  db/              declarative base, async session, models
  api/v1/routes/   health, documents
  schemas/         Pydantic request/response models
alembic/           migration environment and versions
tests/             DB-backed tests skip when Postgres is absent
```

All commands below run from this directory.

```bash
python -m venv ../.venv && ../.venv/Scripts/activate   # or your own venv
pip install -e ".[dev]"
alembic upgrade head
uvicorn parallax.main:app --reload
```

| Command | Effect |
|---|---|
| `pytest` | Tests; DB-backed ones skip without Postgres |
| `ruff check src tests` | Lint |
| `ruff format src tests` | Format |
| `mypy` | Type-check `src/parallax` |
| `alembic revision --autogenerate -m "..."` | New migration |

The `ml` extras (`pip install -e ".[ml]"`) pull Docling, Whisper, torch,
LangGraph, and the vector/object-store clients. They are multi-gigabyte and
deliberately excluded from the default install.
