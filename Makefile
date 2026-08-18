.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: env
env: ## Create .env from the template if missing
	@test -f .env || (cp .env.example .env && echo "created .env")

.PHONY: up
up: env ## Start the full stack
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop the stack (volumes preserved)
	$(COMPOSE) down

.PHONY: nuke
nuke: ## Stop the stack and delete all data volumes
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail API logs
	$(COMPOSE) logs -f api

.PHONY: ps
ps: ## Show service status
	$(COMPOSE) ps

.PHONY: psql
psql: ## Open a psql shell
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-parallax} -d $${POSTGRES_DB:-parallax}

.PHONY: migrate
migrate: ## Apply migrations
	$(COMPOSE) exec api alembic upgrade head

.PHONY: revision
revision: ## Autogenerate a migration: make revision m="add x"
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

.PHONY: downgrade
downgrade: ## Roll back one migration
	$(COMPOSE) exec api alembic downgrade -1

.PHONY: test
test: ## Run the test suite in the API container
	$(COMPOSE) exec api pytest

.PHONY: lint
lint: ## Lint and type-check
	ruff check src tests
	ruff format --check src tests
	mypy

.PHONY: fmt
fmt: ## Auto-format and fix
	ruff format src tests
	ruff check --fix src tests

.PHONY: dev
dev: ## Run the API on the host (needs local Postgres or `make up` for deps)
	uvicorn parallax.main:app --reload --host 127.0.0.1 --port 8000

# --- frontend ---------------------------------------------------------------

.PHONY: web-install
web-install: ## Install frontend dependencies
	cd frontend && npm ci

.PHONY: web-dev
web-dev: ## Run the Vite dev server on the host (proxies /api to :8000)
	cd frontend && npm run dev

.PHONY: web-build
web-build: ## Production build of the frontend
	cd frontend && npm run build

.PHONY: web-lint
web-lint: ## Typecheck, lint, and format-check the frontend
	cd frontend && npm run typecheck && npm run lint && npm run format:check

.PHONY: web-logs
web-logs: ## Tail frontend logs
	$(COMPOSE) logs -f frontend

.PHONY: openapi
openapi: ## Regenerate frontend types from the running API's OpenAPI document
	cd frontend && npm run gen:api

.PHONY: check
check: lint web-lint ## Lint both sides
