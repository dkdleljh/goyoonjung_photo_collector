from __future__ import annotations

import asyncio
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.config import RunConfig
from app.dedup import DedupStore
from app.downloader import ImageDownloader
from app.http_utils import DEFAULT_HEADERS
from app.jsonl_logger import JsonlLogger
from app.models import Candidate
from app.paths import get_photo_root
from app.providers.google import GoogleProvider
from app.providers.instagram_seed import InstagramSeedProvider
from app.providers.naver import NaverImageProvider
from app.providers.twitter_rss import TwitterRSSProvider
from app.providers.twitter_snscrape import TwitterSnScrapeProvider
from app.providers.twitter_rsshub import TwitterRSSHubProvider
from app.providers.wikimedia import WikimediaProvider
from app.time_utils import kst_date_str, kst_timestamp_str
from app.smart_dedup import SmartDedupStore

EXIT_OK = 0
EXIT_DEGRADED = 1
EXIT_ERROR = 2


@dataclass
class RunReport:
    run_ts: str
    dry_run: bool
    providers: list[str]
    candidates_total: int
    unique_urls: int
    counts: Counter
    provider_ok: dict[str, int]
    failures_by_reason: dict[str, int]

    @property
    def ok_count(self) -> int:
        return int(self.counts.get("OK", 0))


class MetricsFailedLogger:
    def __init__(self, base: JsonlLogger) -> None:
        self.base = base
        self.failures_by_reason: Counter[str] = Counter()

    def append(self, data: dict[str, Any]) -> None:
        reason = data.get("reason")
        if isinstance(reason, str) and reason:
            self.failures_by_reason[reason] += 1
        else:
            self.failures_by_reason["UNKNOWN"] += 1
        self.base.append(data)


def _build_provider_tasks(config: RunConfig, project_root: Path) -> list[tuple[str, Any]]:
    tasks: list[tuple[str, Any]] = []
    if "naver" in config.providers:
        tasks.append(("naver", NaverImageProvider(display=config.naver_display, pages=config.naver_pages)))
    if "wikimedia" in config.providers:
        tasks.append(("wikimedia", WikimediaProvider()))
    if "instagram_seed" in config.providers:
        tasks.append(("instagram_seed", InstagramSeedProvider(project_root / "seeds" / "instagram_urls.txt")))
    if "google" in config.providers:
        tasks.append(("google", GoogleProvider(config.keywords, max_pages=config.google_max_pages)))
    if "twitter_rss" in config.providers:
        tasks.append(("twitter_rss", TwitterRSSProvider()))
    if "twitter_snscrape" in config.providers:
        tasks.append(("twitter_snscrape", TwitterSnScrapeProvider(keywords=list(config.keywords))))
    if "twitter_rsshub" in config.providers:
        tasks.append(("twitter_rsshub", TwitterRSSHubProvider(keywords=list(config.keywords))))
    return tasks


async def _collect_with_isolation(
    provider_name: str,
    provider: Any,
    *,
    client: httpx.AsyncClient,
    config: RunConfig,
    failed_logger: MetricsFailedLogger,
    run_ts: str,
) -> list[Candidate]:
    try:
        if provider_name == "naver":
            return await provider.collect(client, config.keywords, failed_logger=failed_logger, now_ts=run_ts)
        return await provider.collect(client, failed_logger=failed_logger, now_ts=run_ts)
    except Exception as exc:  # noqa: BLE001
        failed_logger.append(
            {
                "time_kst": run_ts,
                "provider": provider_name,
                "url": None,
                "reason": "PROVIDER_EXCEPTION",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
        return []


def _build_summary(report: RunReport) -> list[str]:
    lines = [
        f"--- Batch Summary [{report.run_ts}] ---",
        f"dry_run: {report.dry_run}",
        f"providers: {','.join(report.providers)}",
        f"candidates_total: {report.candidates_total}",
        f"unique_urls: {report.unique_urls}",
        f"OK: {report.counts['OK']}",
        f"RESOLUTION_TOO_SMALL: {report.counts['RESOLUTION_TOO_SMALL']}",
        f"DUPLICATE: {report.counts['DUPLICATE']}",
        f"NOT_IMAGE: {report.counts['NOT_IMAGE']}",
        f"IMAGE_DECODE_FAIL: {report.counts['IMAGE_DECODE_FAIL']}",
        f"DOWNLOAD_FAIL: {report.counts['DOWNLOAD_FAIL']}",
        "provider_ok:",
    ]

    if report.provider_ok:
        for provider in sorted(report.provider_ok):
            lines.append(f"  {provider}: {report.provider_ok[provider]}")
    else:
        lines.append("  (no success)")

    lines.append("failures_by_reason:")
    if report.failures_by_reason:
        for reason, value in sorted(report.failures_by_reason.items()):
            lines.append(f"  {reason}: {value}")
    else:
        lines.append("  (none)")

    return lines


def _status_path(root: Path) -> Path:
    return root / "meta" / "status.json"


def _write_status(root: Path, report: RunReport, exit_code: int) -> None:
    prev = read_status() or {}
    prev_err = int(prev.get("consecutive_error", 0) or 0)
    prev_deg = int(prev.get("consecutive_degraded", 0) or 0)

    consecutive_error = prev_err + 1 if exit_code == EXIT_ERROR else 0
    consecutive_degraded = prev_deg + 1 if exit_code == EXIT_DEGRADED else 0

    payload = {
        "last_run_kst": report.run_ts,
        "last_ok_count": report.ok_count,
        "last_exit_code": exit_code,
        "dry_run": report.dry_run,
        "providers": report.providers,
        "candidates_total": report.candidates_total,
        "unique_urls": report.unique_urls,
        "counts": dict(report.counts),
        "failures_by_reason": report.failures_by_reason,
        "consecutive_error": consecutive_error,
        "consecutive_degraded": consecutive_degraded,
        "min_short_side_px": report.counts.get("_min_short_side_px") or None,
    }
    _status_path(root).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_status() -> dict[str, Any] | None:
    root = get_photo_root()
    path = _status_path(root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


async def run_once(config: RunConfig, project_root: Path) -> RunReport:
    root = get_photo_root()
    (root / "meta").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)

    run_ts = kst_timestamp_str()

    items_logger = JsonlLogger(root / "meta" / "items.jsonl")
    failed_logger = MetricsFailedLogger(JsonlLogger(root / "meta" / "failed.jsonl"))
    dedup_store = DedupStore(root / "meta" / "dedup.sqlite")
    smart_dedup = SmartDedupStore(str(root / "meta" / "smart_dedup.pkl"))

    candidates: list[Candidate] = []

    async with httpx.AsyncClient(timeout=25.0, headers=DEFAULT_HEADERS) as client:
        # Collect providers concurrently (isolation keeps failures local)
        tasks = []
        for provider_name, provider in _build_provider_tasks(config, project_root):
            tasks.append(
                _collect_with_isolation(
                    provider_name,
                    provider,
                    client=client,
                    config=config,
                    failed_logger=failed_logger,
                    run_ts=run_ts,
                )
            )

        results = await asyncio.gather(*tasks)
        for provider_candidates in results:
            candidates.extend(provider_candidates)

        candidate_total = len(candidates)
        unique_by_url: dict[str, Candidate] = {}
        for cand in candidates:
            unique_by_url[cand.url] = cand

        unique_candidates = list(unique_by_url.values())
        unique_urls = len(unique_candidates)

        counts: Counter = Counter()
        provider_ok: dict[str, int] = {}

        if config.dry_run:
            counts["DRY_RUN_SKIPPED"] = unique_urls
        else:
            downloader = ImageDownloader(
                root=root,
                dedup_store=dedup_store,
                smart_dedup=smart_dedup,
                items_logger=items_logger,
                failed_logger=failed_logger,
                min_short_side_px=config.min_short_side_px,
            )
            counts, provider_ok = await downloader.process_candidates(
                client,
                unique_candidates,
                workers=config.max_workers,
            )

    dedup_store.close()
    # smart_dedup uses pickle; save is called on updates, but keep a final best-effort save.
    try:
        smart_dedup.save()
    except Exception:
        pass

    # Attach config into counts for status/debug (kept simple & backward compatible)
    counts["_min_short_side_px"] = int(config.min_short_side_px)

    required = [
        "OK",
        "RESOLUTION_TOO_SMALL",
        "DUPLICATE",
        "NOT_IMAGE",
        "IMAGE_DECODE_FAIL",
        "DOWNLOAD_FAIL",
        "DRY_RUN_SKIPPED",
    ]
    for key in required:
        counts.setdefault(key, 0)

    report = RunReport(
        run_ts=run_ts,
        dry_run=config.dry_run,
        providers=config.providers,
        candidates_total=candidate_total,
        unique_urls=unique_urls,
        counts=counts,
        provider_ok=provider_ok,
        failures_by_reason=dict(sorted(failed_logger.failures_by_reason.items())),
    )

    summary_text = "\n".join(_build_summary(report)) + "\n"
    print(summary_text, end="")
    summary_path = root / "logs" / f"summary_{kst_date_str()}.txt"
    try:
        with summary_path.open("a", encoding="utf-8") as fh:
            fh.write(summary_text)
    except OSError as exc:
        print(f"[Collector] Warning: failed to write summary log: {exc}")

    return report


def evaluate_exit_code(report: RunReport) -> int:
    """Exit code policy.

    Production-friendly default:
    - EXIT_OK: run completed and produced *any meaningful outcome* (new OKs or confirmed duplicates).
    - EXIT_DEGRADED: run completed but found nothing (e.g., 0 candidates/0 unique).

    Rationale: on repeated runs, a healthy collector may legitimately produce mostly DUPLICATE.
    """
    if report.ok_count > 0:
        return EXIT_OK

    if report.unique_urls > 0:
        # All duplicates / filtered results still counts as a healthy run.
        return EXIT_OK

    return EXIT_DEGRADED


def run_sync(config: RunConfig, project_root: Path) -> int:
    root = get_photo_root()
    try:
        print("[Collector] Starting batch...")
        report = asyncio.run(run_once(config, project_root))
        exit_code = evaluate_exit_code(report)
        try:
            _write_status(root, report, exit_code)
        except OSError as exc:
            print(f"[Collector] Warning: failed to write status: {exc}")

        # Best-effort notify on repeated degraded/error runs (unmanned ops)
        try:
            from app.notify import notify

            if exit_code == EXIT_ERROR:
                notify(f"[PhotoCollector] ERROR (exit=2) at {report.run_ts}")
            elif exit_code == EXIT_DEGRADED:
                st = read_status() or {}
                if int(st.get("consecutive_degraded", 0) or 0) >= 3:
                    notify(f"[PhotoCollector] DEGRADED x{st.get('consecutive_degraded')} (no meaningful candidates)\nlast_run={report.run_ts}")
        except Exception:
            pass

        print(f"[Collector] Batch finished with exit={exit_code}.")
        return exit_code
    except Exception as exc:  # noqa: BLE001
        fallback = {
            "last_run_kst": kst_timestamp_str(),
            "last_ok_count": 0,
            "last_exit_code": EXIT_ERROR,
            "error": f"{type(exc).__name__}: {exc}",
        }
        try:
            (root / "meta").mkdir(parents=True, exist_ok=True)
            _status_path(root).write_text(json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        print(f"[Collector] Fatal error: {type(exc).__name__}: {exc}")
        return EXIT_ERROR
