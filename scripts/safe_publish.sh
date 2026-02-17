#!/usr/bin/env bash
set -euo pipefail

# Safe publish helper:
# - blocks common secret files
# - runs tests
# - commits (if message provided) and pushes
# - optionally tags/releases

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REMOTE_NAME="${REMOTE_NAME:-public}"
BRANCH="${BRANCH:-main}"

MSG="${1:-}"
BUMP="${BUMP:-}"  # patch|minor|major|none
RELEASE="${RELEASE:-0}"  # 1 to create GH release

fail() { echo "[publish] ERROR: $*" >&2; exit 1; }

# 1) Sanity
command -v git >/dev/null || fail "git not found"
command -v python3 >/dev/null || fail "python3 not found"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  fail "not a git repository"
fi

# Ensure remote exists
if ! git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
  fail "remote '$REMOTE_NAME' not found. (set REMOTE_NAME=... or add remote)"
fi

# Ensure we're on the right branch
CUR_BRANCH="$(git branch --show-current)"
if [[ "$CUR_BRANCH" != "$BRANCH" ]]; then
  fail "current branch is '$CUR_BRANCH' (expected '$BRANCH'). switch first: git checkout $BRANCH"
fi

# 2) Secret guardrails
# Block committing typical secret/state files even if someone staged them.
BLOCKED=(
  ".env" 
  "venv" ".venv" 
  ".run_loop.lock" 
  "collector.log" "collector.loop.log"
)

STAGED="$(git diff --cached --name-only || true)"
for b in "${BLOCKED[@]}"; do
  if echo "$STAGED" | grep -qx "$b"; then
    fail "blocked file is staged: $b"
  fi
  if echo "$STAGED" | grep -q "^${b}/"; then
    fail "blocked directory is staged: ${b}/"
  fi
done

# Naive token scan (best-effort). This is NOT a replacement for real secret scanning.
# We scan staged diff only.
if git diff --cached | grep -E -i "(gho_|github_pat_|xoxb-|xoxp-|AIza|sk-[A-Za-z0-9]{20,}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----|TELEGRAM_BOT_TOKEN|NAVER_CLIENT_SECRET)" >/dev/null; then
  fail "possible secret pattern found in staged diff. inspect with: git diff --cached"
fi

# 3) Tests
if [[ -x "./venv/bin/python" ]]; then
  PY="./venv/bin/python"
elif [[ -x "./.venv/bin/python" ]]; then
  PY="./.venv/bin/python"
else
  fail "no venv python found (venv/ or .venv/)"
fi

"$PY" -m pytest -q

# 4) Commit (optional)
if [[ -n "$MSG" ]]; then
  git add -A
  # re-check blocked after add
  STAGED2="$(git diff --cached --name-only || true)"
  for b in "${BLOCKED[@]}"; do
    if echo "$STAGED2" | grep -qx "$b"; then
      fail "blocked file is staged after git add -A: $b"
    fi
    if echo "$STAGED2" | grep -q "^${b}/"; then
      fail "blocked directory is staged after git add -A: ${b}/"
    fi
  done
  if ! git diff --cached --quiet; then
    git commit -m "$MSG"
  else
    echo "[publish] nothing to commit"
  fi
fi

# 5) Push
# (push only if there are commits ahead)
AHEAD="$(git rev-list --count @{u}..HEAD 2>/dev/null || echo 0)"
if [[ "$AHEAD" == "0" ]]; then
  # still push in case upstream not set
  git push "$REMOTE_NAME" "$BRANCH" || true
else
  git push "$REMOTE_NAME" "$BRANCH"
fi

# 6) Version bump/tag/release (optional)
if [[ -n "$BUMP" && "$BUMP" != "none" ]]; then
  [[ -f VERSION ]] || fail "VERSION file missing"
  VER="$(cat VERSION | tr -d ' \n\r\t')"
  IFS='.' read -r MA MI PA <<<"$VER"
  MA=${MA:-0}; MI=${MI:-0}; PA=${PA:-0}
  case "$BUMP" in
    patch) PA=$((PA+1));;
    minor) MI=$((MI+1)); PA=0;;
    major) MA=$((MA+1)); MI=0; PA=0;;
    *) fail "unknown BUMP=$BUMP (patch|minor|major|none)";;
  esac
  NEW_VER="$MA.$MI.$PA"
  echo "$NEW_VER" > VERSION
  git add VERSION
  git commit -m "chore(release): v$NEW_VER"
  git tag "v$NEW_VER"
  git push "$REMOTE_NAME" "$BRANCH" --tags

  if [[ "$RELEASE" == "1" ]]; then
    command -v gh >/dev/null || fail "gh not found"
    gh release create "v$NEW_VER" --repo "$(git remote get-url "$REMOTE_NAME" | sed -E 's#https://github.com/##; s#\.git$##')" --target "$BRANCH" --title "v$NEW_VER" --notes "Release v$NEW_VER"
  fi
fi

echo "[publish] done"
