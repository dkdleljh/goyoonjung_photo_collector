#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REMOTE_NAME="${REMOTE_NAME:-public}"
BRANCH="${BRANCH:-main}"

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/auto_publish.log"

# Prevent overlapping runs
LOCK_FILE="$ROOT/.auto_publish.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi

stamp() { date '+%Y-%m-%d %H:%M:%S%z'; }
log() { echo "[$(stamp)] $*" >> "$LOG_FILE"; }

# Only allow committing source/docs/config files.
# If there are changes outside this allowlist, we skip (safety).
ALLOWED_RE='^(app/.*\.(py|txt|md)|tests/.*\.(py|sh)|\.github/workflows/.*\.(yml|yaml)|scripts/.*\.(sh|md)|README\.md|사용설명서\.md|reorganize\.py|run_loop\.py|requirements[^/]*\.txt|VERSION|\.gitignore)$'

# Must be inside git
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  log "not a git repo"
  exit 0
fi

# Ensure branch
CUR_BRANCH="$(git branch --show-current)"
if [[ "$CUR_BRANCH" != "$BRANCH" ]]; then
  log "skip: branch=$CUR_BRANCH (expected $BRANCH)"
  exit 0
fi

# If no changes, exit
CHANGED="$(git status --porcelain || true)"
if [[ -z "$CHANGED" ]]; then
  exit 0
fi

# Extract changed file paths (both staged+unstaged)
FILES="$(git status --porcelain | awk '{print $2}' | sed 's#^"##; s#"$##' || true)"

# If any changed file is not allowlisted, skip for safety
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if ! echo "$f" | grep -Eq "$ALLOWED_RE"; then
    log "skip: disallowed change detected: $f"
    exit 0
  fi
  # Also skip if looks like a binary asset accidentally added
  if file -b --mime "$f" 2>/dev/null | grep -qE 'application/octet-stream|image/|video/|audio/'; then
    log "skip: binary-like file detected: $f"
    exit 0
  fi
done <<< "$FILES"

# Stage allowlisted files only
git reset -q
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  git add "$f"
done <<< "$FILES"

if git diff --cached --quiet; then
  exit 0
fi

# Use the safe_publish guardrails for secret scanning + tests + push.
MSG="chore(auto): sync $(date '+%Y-%m-%d %H:%M KST')"
log "publishing: $MSG"

# Call safe_publish, but without re-adding everything (it does git add -A if MSG is provided).
# So we commit and push here using the same checks as safe_publish.

# Blocklist check (mirrors safe_publish)
STAGED="$(git diff --cached --name-only || true)"
BLOCKED=(".env" "venv" ".venv" ".run_loop.lock" "collector.log" "collector.loop.log")
for b in "${BLOCKED[@]}"; do
  if echo "$STAGED" | grep -qx "$b"; then
    log "blocked file staged: $b"; git reset -q; exit 1
  fi
  if echo "$STAGED" | grep -q "^${b}/"; then
    log "blocked dir staged: ${b}/"; git reset -q; exit 1
  fi
done

if git diff --cached | grep -E -i "(gho_|github_pat_|xoxb-|xoxp-|AIza|sk-[A-Za-z0-9]{20,}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----|TELEGRAM_BOT_TOKEN|NAVER_CLIENT_SECRET)" >/dev/null; then
  log "possible secret pattern in staged diff"; git reset -q; exit 1
fi

# Run tests
if [[ -x "./venv/bin/python" ]]; then
  PY="./venv/bin/python"
elif [[ -x "./.venv/bin/python" ]]; then
  PY="./.venv/bin/python"
else
  log "no venv python found"; git reset -q; exit 1
fi

"$PY" -m pytest -q >> "$LOG_FILE" 2>&1

git commit -m "$MSG" >> "$LOG_FILE" 2>&1 || { log "commit failed"; exit 1; }

git push "$REMOTE_NAME" "$BRANCH" >> "$LOG_FILE" 2>&1 || { log "push failed"; exit 1; }

log "done"
