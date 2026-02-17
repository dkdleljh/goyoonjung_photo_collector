from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

INTERVAL_HOURS = 4
PROJECT_ROOT = Path("/home/zenith/Desktop/goyoonjung_photo_collector")
PYTHON_EXE = PROJECT_ROOT / "venv" / "bin" / "python"
FALLBACK_PY = PROJECT_ROOT / ".venv" / "bin" / "python"

SMOKE_TIMEOUT_SEC = 120
SMOKE_TEST = PROJECT_ROOT / "tests" / "smoke_test.sh"
SMOKE_ROOT = PROJECT_ROOT / ".smoke_photo_root"

if not PYTHON_EXE.exists():
    # fallback for older installs. Prefer venv/ to keep a single source of truth.
    PYTHON_EXE = FALLBACK_PY
LOCK_FILE = PROJECT_ROOT / ".run_loop.lock"


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _acquire_lock() -> None:
    if LOCK_FILE.exists():
        try:
            existing_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            existing_pid = -1
        if existing_pid > 0 and _is_process_alive(existing_pid):
            print(f"[Loop] Another run_loop is active (pid={existing_pid}). Exiting.")
            raise SystemExit(1)
        LOCK_FILE.unlink(missing_ok=True)

    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def _run_smoke() -> tuple[int, str]:
    if not SMOKE_TEST.exists():
        return 0, "missing smoke_test.sh (skip)"

    try:
        SMOKE_ROOT.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PHOTO_ROOT"] = str(SMOKE_ROOT)

    proc = subprocess.Popen(
        ["bash", str(SMOKE_TEST)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        out, _ = proc.communicate(timeout=SMOKE_TIMEOUT_SEC)
        return int(proc.returncode), out
    except subprocess.TimeoutExpired:
        proc.send_signal(signal.SIGTERM)
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
        return 124, (out or "") + "\n[smoke] timeout"


def _run_cycle(args: argparse.Namespace) -> int:
    started = datetime.now()
    print(f"\n[Loop] Starting collection at {started.strftime('%Y-%m-%d %H:%M:%S')}")

    # pre-flight smoke test (recommended): fast, local-only.
    smoke_code, smoke_out = _run_smoke()
    if smoke_out:
        print(smoke_out, end="" if smoke_out.endswith("\n") else "\n")
    if smoke_code not in (0, 1):
        print(f"[Loop] Smoke test failed (exit={smoke_code}). Skipping this cycle.")
        return 1

    # Use -u (unbuffered) so logs are flushed promptly in long-running service mode.
    cmd = [str(PYTHON_EXE), "-u", "-m", "app.cli", "run", "--once"]
    if args.providers:
        cmd.extend(["--providers", args.providers])
    if args.keywords:
        cmd.extend(["--keywords", args.keywords])
    if args.dry_run:
        cmd.append("--dry-run")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output, _ = proc.communicate(timeout=args.timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.send_signal(signal.SIGTERM)
        try:
            output, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()
        print(output, end="")
        print(f"[Loop] Collection timed out after {args.timeout_seconds}s")
        return 124

    print(output, end="")
    ended = datetime.now()
    seconds = int((ended - started).total_seconds())
    print(f"[Loop] Collection finished with exit={proc.returncode} in {seconds}s")

    if proc.returncode == 0 and not args.dry_run and not args.skip_reorganize:
        reorg_cmd = [str(PYTHON_EXE), "reorganize.py"]
        reorg = subprocess.run(reorg_cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
        print(reorg.stdout, end="")
        if reorg.returncode != 0:
            print(reorg.stderr, end="")
            print(f"[Loop] Reorganize failed with exit={reorg.returncode}")
        else:
            print("[Loop] Reorganize completed.")

    return int(proc.returncode)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run collector every N hours.")
    parser.add_argument("--interval-hours", type=float, default=INTERVAL_HOURS)
    parser.add_argument("--providers", default="")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--skip-reorganize", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _acquire_lock()
    print(f"[Loop] Collector service started. interval_hours={args.interval_hours}")
    print(f"[Loop] python: {PYTHON_EXE}")
    if (PROJECT_ROOT / ".venv").exists() and (PROJECT_ROOT / "venv").exists():
        print("[Loop] NOTE: both venv/ and .venv/ exist. run_loop prefers venv/. Consider removing .venv/ after confirming.")
    try:
        while True:
            code = _run_cycle(args)
            if args.once:
                raise SystemExit(code)

            sleep_seconds = max(1, int(args.interval_hours * 3600))
            print(f"[Loop] Sleeping for {sleep_seconds}s")
            time.sleep(sleep_seconds)
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
