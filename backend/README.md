# PARALLAX — backend

The FastAPI service and the agent system. Project overview and the pipeline
diagram are in the [root README](../README.md).

```
src/parallax/
  main.py          app factory + ASGI entrypoint
  core/            settings, logging, domain exceptions
  llm/client.py    OpenAI-compatible chat client
  tools/           Tool registry + the canned mobile and computer toolsets
  agents/          ToolAgent loop, the two specialists, the supervisor
  api/v1/routes/   health, support
  schemas/         request/response models
tests/             54 tests; every LLM call is stubbed
```

All commands below run from this directory.

```bash
pip install -e ".[dev]"
uvicorn parallax.main:app --reload
```

| Command | Effect |
|---|---|
| `pytest` | Full suite. No model server or network needed. |
| `ruff check src tests` | Lint |
| `ruff format src tests` | Format |
| `mypy` | Type-check `src/parallax` |

The agent talks to any OpenAI-compatible server via `PARALLAX_LLM_BASE_URL`
(default Ollama). Config lives in `core/config.py`; the full list of settings is
in [`.env.example`](../.env.example).
