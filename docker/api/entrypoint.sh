#!/usr/bin/env bash
set -euo pipefail

# Compose gates startup on the postgres healthcheck, but a healthy container is
# not the same as an accepting connection, so retry briefly before giving up.
if [[ "${PARALLAX_RUN_MIGRATIONS:-true}" == "true" ]]; then
  for attempt in {1..12}; do
    if alembic upgrade head; then
      echo "[entrypoint] migrations applied"
      break
    fi
    if [[ "${attempt}" == "12" ]]; then
      echo "[entrypoint] migrations failed after ${attempt} attempts" >&2
      exit 1
    fi
    echo "[entrypoint] migration attempt ${attempt} failed, retrying in 5s"
    sleep 5
  done
fi

exec "$@"
