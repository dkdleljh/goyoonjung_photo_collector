#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Scan staged changes (fast) and optionally full repo.
MODE="${1:-staged}" # staged|full

fail() { echo "[secret_scan] ERROR: $*" >&2; exit 1; }

command -v git >/dev/null || fail "git not found"

# 1) gitleaks (preferred)
if command -v gitleaks >/dev/null 2>&1; then
  if [[ "$MODE" == "staged" ]]; then
    # gitleaks cannot scan git index directly reliably without a commit,
    # so we scan the staged diff content by creating a temporary patch file.
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' EXIT
    git diff --cached > "$tmp" || true
    # If nothing staged, exit ok.
    if [[ ! -s "$tmp" ]]; then
      exit 0
    fi

    # Best-effort: scan patch as file.
    gitleaks detect --no-git --source "$tmp" -c .gitleaks.toml --redact --verbose || fail "gitleaks found leaks in staged diff"
    exit 0
  fi

  # Full repo scan
  gitleaks detect --source . -c .gitleaks.toml --redact --verbose || fail "gitleaks found leaks"
  exit 0
fi

# 2) git-secrets fallback (works on repo content; staged diff via git diff)
if command -v git-secrets >/dev/null 2>&1; then
  if [[ "$MODE" == "staged" ]]; then
    git diff --cached | git-secrets --scan - || fail "git-secrets found leaks in staged diff"
  else
    git secrets --scan || fail "git-secrets found leaks"
  fi
  exit 0
fi

# 3) Minimal grep fallback
if git diff --cached | grep -E -i "(gho_|github_pat_|xoxb-|xoxp-|AIza|sk-[A-Za-z0-9]{20,}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----|TELEGRAM_BOT_TOKEN|NAVER_CLIENT_SECRET)" >/dev/null; then
  fail "possible secret pattern found"
fi

exit 0
