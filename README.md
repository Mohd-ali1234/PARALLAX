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
| Agents | LangGraph |
| LLM | Claude (default), GPT, Qwen |
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
`test`, `lint`, `nuke`).

### Running the API without Docker

You still need a Postgres with the `vector` extension. Point `.env` at it
(`PARALLAX_POSTGRES_HOST=localhost`), then:

```bash
python -m venv .venv && .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
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

```
alembic/                  migration environment and versions
docker/
  api/Dockerfile          multi-stage build (builder → runtime → dev)
  frontend/Dockerfile     node build → nginx runtime, plus a Vite dev target
  frontend/nginx.conf     SPA fallback + /api proxy to the api service
  postgres/init/          extensions created on first volume init
frontend/
  src/api/                fetch client, typed schemas, TanStack Query hooks
  src/components/         ServiceStatus, DocumentTable
src/parallax/
  main.py                 app factory + ASGI entrypoint
  core/                   settings, logging, domain exceptions
  db/                     declarative base, async session, models
  api/v1/routes/          health, documents
  schemas/                Pydantic request/response models
tests/                    DB-backed tests skip when Postgres is absent
```

## Configuration

All settings come from the environment with the `PARALLAX_` prefix and are
declared once in [`core/config.py`](src/parallax/core/config.py). `.env.example`
is the full list. Secrets are never committed; `.env` is gitignored.

## Tests

```bash
pytest                # DB-backed tests skip without Postgres
make test             # runs inside the API container, DB present
```
