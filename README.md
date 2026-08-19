# PARALLAX

**Multimodal Financial Verification Engine.**

PARALLAX ingests the same financial period from four independent channels — SEC
filings, investor decks, earnings-call audio, and XBRL facts — normalizes every
numeric assertion into a *claim*, and then checks the channels against each
other. Where they disagree, it says so and shows the evidence.

> Status: **scaffold**. Infrastructure, API skeleton, and the claim schema are in
> place. Ingestion, agents, and reconciliation are not yet implemented.

---

## Architecture

### Offline ingestion

```
Ingestion Orchestrator
  ├── SEC Filing    → PDF Parser (Docling)
  ├── Investor Deck → PDF Renderer
  ├── Audio         → Whisper
  └── XBRL Facts    → XBRL Parser
                         │
              Claim Extraction Layer
                         │
                   Claim Manager
        (normalize · merge · resolve entities ·
         relate · store provenance · embed)
                         │
        ┌────────────────┴────────────────┐
   PostgreSQL                    Qdrant / pgvector
   claims + metadata              semantic search
```

### Online query

```
User Question → Supervisor Agent
                     │
   ┌────────────┬────┴───────┬────────────┐
Filing Agent  Deck Agent  Audio Agent  XBRL Agent
   └────────────┴────────────┴────────────┘
                     │
        Reconciliation Engine (pure Python)
                     │
             Verification Agent
                     │
                Critic Agent
                     │
           Reporter + Evidence
```

The reconciliation engine is deliberately **not** an LLM. Agents retrieve and
extract; arithmetic agreement is decided by deterministic code so the verdict is
reproducible.

---

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI, Uvicorn, Pydantic v2 |
| Web client | React 19, TypeScript, Vite, TanStack Query |
| Database | PostgreSQL 16 + pgvector, SQLAlchemy 2.0 (async), Alembic |
| Vector search | Qdrant (pgvector available as a fallback) |
| Cache / queue | Redis 7 |
| Object storage | MinIO |
| Parsing | Docling |
| Speech | Whisper |
| Embeddings | BGE-M3 (1024-d) |
| Reranking | BGE-Reranker-v2-m3 |
| Agents | hand-rolled tool loop today; LangGraph for the supervisor graph |
| LLM | any OpenAI-compatible server (Ollama, LM Studio, llama.cpp, vLLM) |
| Tracing | Langfuse |
| Runtime | Docker Compose |

---

## Quick start

Requires **Docker Desktop** (Compose v2). Nothing else needs to be installed.

```bash
cp .env.example .env        # or: make env
docker compose up -d --build
```

The API entrypoint runs `alembic upgrade head` before serving, so the schema is
created on first boot.

| Service | URL |
|---|---|
| Web app | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Liveness | http://localhost:8000/api/v1/health/live |
| Readiness (checks Postgres) | http://localhost:8000/api/v1/health/ready |
| Qdrant dashboard | http://localhost:6333/dashboard |
| MinIO console | http://localhost:9001 |
| Postgres | `localhost:5432` |

Smoke test:

```bash
curl -s localhost:8000/api/v1/health/ready
```

`make help` lists the shortcuts (`up`, `down`, `logs`, `psql`, `migrate`,
`test`, `lint`, `nuke`). The Makefile is a convenience only — `make` is not
installed by default on Windows, and every target is a one-line `docker compose`
or `cd backend && ...` command you can run directly.

### Running the API without Docker

You still need a Postgres with the `vector` extension. Point `.env` at it
(`PARALLAX_POSTGRES_HOST=localhost`), then:

```bash
python -m venv .venv && .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -e "./backend[dev]"

cd backend            # alembic.ini and pyproject.toml live here
alembic upgrade head
uvicorn parallax.main:app --reload
```

Use Python **3.12** — the `ml` extras (torch, docling, whisper) do not have
complete 3.13 wheels yet.

---

## Frontend

React 19 + TypeScript on Vite, in [`frontend/`](frontend/). It currently renders
the service-readiness pill and the document registry — enough to prove the
browser, API, and database are genuinely connected. The agent and evidence views
come later.

```bash
cd frontend
npm ci
npm run dev          # http://localhost:5173
```

**The browser never makes a cross-origin request.** In dev, Vite proxies `/api`
to FastAPI; in the production image, nginx does the same to the `api` service.
So `VITE_API_BASE_URL` is empty by default and the backend's CORS list only
matters if you deliberately run the frontend against a different host.

| Command | Effect |
|---|---|
| `npm run dev` | Dev server with HMR, proxying `/api` |
| `npm run build` | Typecheck then production bundle to `dist/` |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm run lint` | ESLint 9 flat config, type-aware rules |
| `npm run gen:api` | Regenerate types from the running API's OpenAPI doc |

### Keeping types honest

[`src/api/types.ts`](frontend/src/api/types.ts) is written by hand to mirror the
Pydantic schemas, so the app type-checks with no backend running. That means it
can drift. When you change a schema, run `make openapi` against a live API to
regenerate from the source of truth.

[`src/api/client.ts`](frontend/src/api/client.ts) unwraps both error shapes the
backend can produce: the `{"error": {code, message, details}}` envelope from
`register_exception_handlers`, and FastAPI's own `{"detail": [...]}` for 422s.
Both surface as a typed `ApiError` with `.status` and `.code`.

---

## AI agent

A small tool-calling agent lives in [`backend/src/parallax/ai/`](backend/src/parallax/ai/).
Ask it a question, it calls tools against the document registry, and answers
from what they returned.

```bash
curl -s localhost:8000/api/v1/agent/tools          # what it can call
curl -s -X POST localhost:8000/api/v1/agent/ask   -H 'Content-Type: application/json'   -d '{"question": "how many earnings calls are ingested?"}'
```

The response carries the tool calls that produced it — PARALLAX shows its work:

```json
{
  "answer": "There is 1 earnings call ingested.",
  "steps": [{"tool": "count_documents", "arguments": "{\"source_type\":\"earnings_call\"}",
             "result": "1 document(s) of type earnings_call."}],
  "iterations": 2, "stop_reason": "final_answer", "model": "qwen2.5:7b"
}
```

### Pointing it at a local model

The client speaks the **OpenAI-compatible** `/v1/chat/completions` API, so the
runtime is a config value, not a code change:

| Runtime | `PARALLAX_LLM_BASE_URL` |
|---|---|
| Ollama (default) | `http://localhost:11434/v1` |
| LM Studio | `http://localhost:1234/v1` |
| llama.cpp server | `http://localhost:8080/v1` |
| vLLM | `http://localhost:8000/v1` |

```bash
ollama serve
ollama pull qwen2.5:7b        # must support tool calling
```

**The model must support tool calling.** A model without it answers from the
prompt alone and silently ignores the tools — for a verification engine that is
the worst failure mode there is, because it still looks like an answer. If
`steps` comes back empty on a question that clearly needs data, that is the tell.

Some models (`qwen2.5-coder` among them) advertise tool support and then write
the call into the message text instead of the `tool_calls` field. The client
recovers those: if the text parses as JSON naming a tool we actually offered, it
is promoted to a real call. Anything else is left alone, so a genuine answer is
never mistaken for a call. `qwen2.5`, `llama3.1` and `mistral-nemo` need no such
help.

From inside Docker, `localhost` is the container. Use
`PARALLAX_LLM_BASE_URL=http://host.docker.internal:11434/v1` to reach a model
server on the host.

If the server is not running, `/agent/ask` returns a `503` naming the URL it
tried, rather than hanging.

### How it works

Four small pieces, no agent framework:

- [`llm.py`](backend/src/parallax/ai/llm.py) — one `chat()` method over httpx.
- [`tools.py`](backend/src/parallax/ai/tools.py) — a registry mapping names to
  async functions plus their JSON schema. Schemas are hand-written, because for
  tool calling the description *is* the interface.
- [`builtin_tools.py`](backend/src/parallax/ai/builtin_tools.py) — three
  read-only tools over the `documents` table.
- [`agent.py`](backend/src/parallax/ai/agent.py) — the loop: ask, run any
  requested tools, feed results back, repeat until the model answers or
  `PARALLAX_AGENT_MAX_ITERATIONS` is hit.

Two decisions worth knowing:

**Model mistakes are fed back, infrastructure failures are raised.** An unknown
tool name, malformed JSON arguments, or wrong parameters come back to the model
as an observation it can correct — aborting the run would throw away an answer
it could still reach. A database outage propagates as a 5xx, because retrying
will not help.

**The tools are read-only.** An agent that can mutate ingestion state is a much
larger conversation about authorization than this scaffold should settle.

It is hand-rolled rather than LangGraph on purpose: the loop is ~40 lines and
adds no dependency. LangGraph earns its place when the supervisor/critic graph
from the architecture lands — it does not yet.

---

## Data model

Four tables carry the ingestion output. Everything downstream reads from them.

- **`entities`** — companies, segments, products, people. Claims and documents
  resolve to one.
- **`documents`** — one row per source artifact. Bytes live in MinIO
  (`storage_uri`); `checksum` is unique, which makes re-ingestion idempotent.
  `status` tracks it through `pending → parsing → extracting → indexed`.
- **`claims`** — one normalized numeric assertion. `canonical_key` is the join
  the reconciliation engine groups on: two claims sharing a key and a period
  must agree, whichever modality produced them. `modality` records which lane it
  came from (`text`, `table`, `chart`, `audio`, `structured`), and `embedding`
  is a 1024-d pgvector column for semantic lookup.
- **`claim_provenance`** — how a claim is proved. `locator` is JSONB because the
  anchor is modality-specific: `{page, bbox}` for PDFs, `{start_s, end_s}` for
  audio, `{row, col}` for tables, `{context_ref}` for XBRL. Every claim surfaced
  to a user must carry at least one.

### Migrations

```bash
make revision m="add reconciliation results"   # autogenerate
make migrate                                   # apply
make downgrade                                 # roll back one
```

CI asserts that every migration applies, reverses to `base`, and reapplies —
write reversible `downgrade()` bodies.

`embedding` is pinned to 1024 dimensions in the initial migration rather than
read from settings. Changing the embedding model means a new migration.

---

## Layout

Backend and frontend are siblings; everything that runs the stack sits at the root.

```
backend/                  the FastAPI service
  pyproject.toml          deps, ruff/mypy/pytest config
  alembic.ini
  alembic/                migration environment and versions
  src/parallax/
    main.py               app factory + ASGI entrypoint
    ai/                   LLM client, tool registry, agent loop
    core/                 settings, logging, domain exceptions
    db/                   declarative base, async session, models
    api/v1/routes/        health, documents, agent
    schemas/              Pydantic request/response models
  tests/                  DB-backed tests skip when Postgres is absent

frontend/                 the React client
  src/api/                fetch client, typed schemas, TanStack Query hooks
  src/components/         ServiceStatus, DocumentTable
  vite.config.ts          dev server + /api proxy

docker/
  api/Dockerfile          multi-stage build (builder → runtime → dev)
  frontend/Dockerfile     node build → nginx runtime, plus a Vite dev target
  frontend/nginx.conf     SPA fallback + /api proxy to the api service
  postgres/init/          extensions created on first volume init

docker-compose.yml        the whole stack
Makefile                  shortcuts; backend targets cd into backend/ for you
```

Python tooling is configured once in `backend/pyproject.toml`, and every path in
it is relative to that file — so `ruff`, `mypy`, `pytest`, and `alembic` must be
run from `backend/`. The Makefile targets handle that; `make lint`, `make fmt`,
and `make dev` still work from the repo root.


## Configuration

All settings come from the environment with the `PARALLAX_` prefix and are
declared once in [`core/config.py`](backend/src/parallax/core/config.py). `.env.example`
is the full list. Secrets are never committed; `.env` is gitignored.

## Tests

```bash
cd backend && pytest  # DB-backed tests skip without Postgres
make test             # runs inside the API container, DB present
```
