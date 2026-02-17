from __future__ import annotations

import asyncio
import hashlib
# imghdr removed (deprecated in Python 3.13)
import random
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import httpx
from PIL import Image

from app.http_utils import request_with_retry
from app.models import Candidate
from app.time_utils import kst_timestamp_str


def _guess_extension(url: str, content_type: str | None, data: bytes, img_format: str | None = None) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name.lower()
    if "." in name:
        suffix = "." + name.rsplit(".", 1)[-1]
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}:
            return suffix

    if content_type:
        ct = content_type.lower()
        if "jpeg" in ct:
            return ".jpg"
        if "png" in ct:
            return ".png"
        if "webp" in ct:
            return ".webp"
        if "gif" in ct:
            return ".gif"
        if "bmp" in ct:
            return ".bmp"
        if "tiff" in ct:
            return ".tiff"

    # Pillow-based detection (imghdr is deprecated)
    fmt = (img_format or "").strip().lower()
    if not fmt:
        try:
            with Image.open(BytesIO(data)) as im:
                fmt = (im.format or "").strip().lower()
        except Exception:
            fmt = ""

    if fmt in {"jpeg", "jpg"}:
        return ".jpg"
    if fmt in {"png", "webp", "gif", "bmp", "tiff"}:
        return f".{fmt}"
    return ".img"


def _is_720p_or_above(width: int, height: int) -> bool:
    min_side = 300
    return width >= min_side or height >= min_side


class ImageDownloader:
    def __init__(self, root: Path, dedup_store, items_logger, failed_logger) -> None:
        self.root = root
        self.dedup_store = dedup_store
        self.items_logger = items_logger
        self.failed_logger = failed_logger

    async def process_candidates(
        self,
        client: httpx.AsyncClient,
        candidates: Iterable[Candidate],
        workers: int,
    ) -> tuple[Counter, dict[str, int]]:
        queue: asyncio.Queue[Candidate] = asyncio.Queue()
        for c in candidates:
            queue.put_nowait(c)

        counts: Counter = Counter()
        provider_ok: dict[str, int] = {}
        lock = asyncio.Lock()

        async def worker() -> None:
            while True:
                try:
                    cand = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return

                reason = await self._download_one(client, cand)
                async with lock:
                    counts[reason] += 1
                    if reason == "OK":
                        provider_ok[cand.provider] = provider_ok.get(cand.provider, 0) + 1
                queue.task_done()

        tasks = [asyncio.create_task(worker()) for _ in range(max(1, workers))]
        await asyncio.gather(*tasks)
        return counts, provider_ok

    async def _download_one(self, client: httpx.AsyncClient, cand: Candidate) -> str:
        time_kst = kst_timestamp_str()
        try:
            await asyncio.sleep(random.uniform(0.8, 1.6))
            resp = await request_with_retry(
                client,
                "GET",
                cand.url,
                retries=3,
                polite_delay=False,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            self.failed_logger.append(
                {
                    "time_kst": time_kst,
                    "provider": cand.provider,
                    "url": cand.url,
                    "source_url": cand.source_url,
                    "reason": "DOWNLOAD_FAIL",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
            return "DOWNLOAD_FAIL"

        content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            self.failed_logger.append(
                {
                    "time_kst": time_kst,
                    "provider": cand.provider,
                    "url": cand.url,
                    "source_url": cand.source_url,
                    "reason": "NOT_IMAGE",
                    "detail": f"content_type={content_type or 'unknown'}",
                }
            )
            return "NOT_IMAGE"

        data = resp.content

        try:
            with Image.open(BytesIO(data)) as img:
                width, height = img.size
                img_format = (img.format or "")
        except Exception as exc:  # noqa: BLE001
            self.failed_logger.append(
                {
                    "time_kst": time_kst,
                    "provider": cand.provider,
                    "url": cand.url,
                    "source_url": cand.source_url,
                    "reason": "IMAGE_DECODE_FAIL",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
            return "IMAGE_DECODE_FAIL"

        if not _is_720p_or_above(width, height):
            self.failed_logger.append(
                {
                    "time_kst": time_kst,
                    "provider": cand.provider,
                    "url": cand.url,
                    "source_url": cand.source_url,
                    "reason": "RESOLUTION_TOO_SMALL",
                    "detail": f"{width}x{height}",
                }
            )
            return "RESOLUTION_TOO_SMALL"

        sha256_hex = hashlib.sha256(data).hexdigest()
        if self.dedup_store.has(sha256_hex):
            self.failed_logger.append(
                {
                    "time_kst": time_kst,
                    "provider": cand.provider,
                    "url": cand.url,
                    "source_url": cand.source_url,
                    "reason": "DUPLICATE",
                    "detail": sha256_hex,
                }
            )
            return "DUPLICATE"

        date_str = time_kst[:10]
        save_dir = self.root / date_str / cand.provider
        save_dir.mkdir(parents=True, exist_ok=True)

        ext = _guess_extension(cand.url, content_type, data, img_format=img_format)
        filename = f"{sha256_hex[:20]}{ext}"
        save_path = save_dir / filename

        save_path.write_bytes(data)
        self.dedup_store.add(sha256_hex, time_kst)

        if width >= 3000 or len(data) >= 2 * 1024 * 1024:
            self._save_copy(data, filename, "Organized/Best_Cuts")

        if max(width, height) >= 1920:
            if height > width:
                self._save_copy(data, filename, "Organized/Mobile_Wallpapers")
            else:
                self._save_copy(data, filename, "Organized/Desktop_Wallpapers")
        elif max(width, height) >= 1000:
            self._save_copy(data, filename, "Organized/General_HQ")
        else:
            self._save_copy(data, filename, "Organized/Archive_LowRes")

        self.items_logger.append(
            {
                "time_kst": time_kst,
                "provider": cand.provider,
                "query": cand.query,
                "url": cand.url,
                "source_url": cand.source_url,
                "saved_path": str(save_path),
                "width": width,
                "height": height,
                "sha256": sha256_hex,
                "content_type": content_type,
                "content_length": len(data),
            }
        )
        return "OK"

    def _save_copy(self, data: bytes, filename: str, subpath: str) -> None:
        target_dir = self.root / subpath
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / filename).write_bytes(data)
