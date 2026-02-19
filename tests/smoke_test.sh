#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SMOKE_ROOT="${ROOT_DIR}/.smoke_photo_root"
if [[ -x "${ROOT_DIR}/venv/bin/python" ]]; then
  PY_BIN="${ROOT_DIR}/venv/bin/python"
elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PY_BIN="${ROOT_DIR}/.venv/bin/python"
else
  echo "[smoke] no virtualenv python found"
  exit 1
fi

echo "[smoke] run dry-run with local-only provider"
mkdir -p "$SMOKE_ROOT"
set +e
PHOTO_ROOT="$SMOKE_ROOT" "$PY_BIN" -m app.cli run --providers "instagram_seed" --dry-run --once
RUN_CODE=$?
set -e
if [[ "$RUN_CODE" -ne 0 && "$RUN_CODE" -ne 1 ]]; then
  echo "[smoke] unexpected run exit code: $RUN_CODE"
  exit 1
fi

# NOTE:
# We intentionally do NOT run `app.cli status` here.
# The dry-run may produce 0 candidates and mark status as degraded (exit=1),
# which is expected and should not be treated as a bot failure.

echo "[smoke] ok (run_exit=$RUN_CODE)"
