from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.http_utils import request_with_retry
from app.models import Candidate


def _is_direct_image_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


class InstagramSeedProvider:
    name = "instagram_seed"

    def __init__(self, seed_path: Path) -> None:
        self.seed_path = seed_path

    async def collect(self, client: httpx.AsyncClient, failed_logger, now_ts: str) -> list[Candidate]:
        if not self.seed_path.exists():
            return []

        seeds: list[str] = []
        for line in self.seed_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            seeds.append(line)

        candidates: list[Candidate] = []
        for seed in seeds:
            if _is_direct_image_url(seed):
                candidates.append(Candidate(url=seed, provider=self.name, source_url=seed))
                continue

            try:
                resp = await request_with_retry(
                    client,
                    "GET",
                    seed,
                    retries=3,
                    polite_delay=True,
                    follow_redirects=True,
                )

                if resp.status_code in {401, 403, 429}:
                    failed_logger.append(
                        {
                            "time_kst": now_ts,
                            "provider": self.name,
                            "url": seed,
                            "reason": "INSTAGRAM_LOGIN_OR_BLOCKED",
                            "detail": f"status={resp.status_code}",
                        }
                    )
                    continue

                html = resp.text
                soup = BeautifulSoup(html, "lxml")
                meta = soup.find("meta", attrs={"property": "og:image"})
                content = meta.get("content") if meta else None
                if isinstance(content, str) and content.startswith("http"):
                    candidates.append(Candidate(url=content, provider=self.name, source_url=seed))
                else:
                    failed_logger.append(
                        {
                            "time_kst": now_ts,
                            "provider": self.name,
                            "url": seed,
                            "reason": "OG_IMAGE_NOT_FOUND",
                            "detail": "og:image meta를 찾지 못함",
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                failed_logger.append(
                    {
                        "time_kst": now_ts,
                        "provider": self.name,
                        "url": seed,
                        "reason": "DOWNLOAD_FAIL",
                        "detail": f"error={type(exc).__name__}: {exc}",
                    }
                )

        return candidates
