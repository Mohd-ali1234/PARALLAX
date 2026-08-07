# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# PARALLAX API image. Python 3.12 (not 3.13) because the ingestion extras
# (torch / docling / whisper) still lag on 3.13 wheels.
# ---------------------------------------------------------------------------

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip setuptools wheel && pip install .


# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 parallax

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=parallax:parallax alembic.ini ./
COPY --chown=parallax:parallax alembic ./alembic
COPY --chown=parallax:parallax src ./src
COPY --chown=parallax:parallax docker/api/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER parallax
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health/live || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "parallax.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ---------------------------------------------------------------------------
# Dev stage: editable install so the bind-mounted ./src is what actually runs.
FROM runtime AS dev

USER root
COPY --chown=parallax:parallax pyproject.toml README.md /app/
RUN pip install --no-cache-dir -e "/app[dev]"
USER parallax
CMD ["uvicorn", "parallax.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/app/src"]
