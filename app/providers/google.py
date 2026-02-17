from __future__ import annotations

import asyncio
import logging
import random
import re
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from app.http_utils import request_with_retry
from app.models import Candidate

LOGGER = logging.getLogger(__name__)


class GoogleProvider:
    name = "google"

    def __init__(self, keywords: list[str], max_pages: int = 1):
        self.keywords = keywords
        self.max_pages = max_pages

    async def collect(self, client: httpx.AsyncClient, failed_logger, now_ts: str) -> list[Candidate]:
        candidates: list[Candidate] = []
        for kw in self.keywords:
            search_queries = [kw, f"{kw} 고화질", f"{kw} wallpaper"]
            for q in search_queries[: self.max_pages + 2]:
                url = f"https://www.google.com/search?q={quote(q)}&tbm=isch&tbs=isz:l"
                try:
                    await asyncio.sleep(random.uniform(0.8, 1.6))
                    resp = await request_with_retry(
                        client,
                        "GET",
                        url,
                        retries=3,
                        polite_delay=False,
                        follow_redirects=True,
                    )
                    if resp.status_code != 200:
                        failed_logger.append(
                            {
                                "time_kst": now_ts,
                                "provider": self.name,
                                "url": url,
                                "reason": "DOWNLOAD_FAIL",
                                "detail": f"query={q}, status={resp.status_code}",
                            }
                        )
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    for img in soup.find_all("img"):
                        src = img.get("src") or img.get("data-src")
                        if isinstance(src, str) and src.startswith("http"):
                            if "google" in src or "logo" in src:
                                continue
                            candidates.append(Candidate(provider=self.name, query=q, url=src, source_url=url))

                    for link in re.findall(r'(https?://[^"\']+\.(?:jpg|jpeg|png|webp))', resp.text):
                        if "gstatic" in link or "favicon" in link:
                            continue
                        decoded = link.replace("\\u003d", "=").replace("\\u0026", "&")
                        candidates.append(Candidate(provider=self.name, query=q, url=decoded, source_url=url))
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("[Google] query failed: %s (%s)", q, exc)
                    failed_logger.append(
                        {
                            "time_kst": now_ts,
                            "provider": self.name,
                            "url": url,
                            "reason": "DOWNLOAD_FAIL",
                            "detail": f"query={q}, error={type(exc).__name__}: {exc}",
                        }
                    )

        return candidates
