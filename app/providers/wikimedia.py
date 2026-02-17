from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.http_utils import request_with_retry
from app.models import Candidate


class WikimediaProvider:
    name = "wikimedia"
    endpoint = "https://commons.wikimedia.org/w/api.php"

    async def collect(self, client: httpx.AsyncClient, failed_logger, now_ts: str) -> list[Candidate]:
        queries = ["Go Yoon-jung", "고윤정"]
        candidates: list[Candidate] = []

        for q in queries:
            params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": f"filetype:bitmap {q}",
                "gsrnamespace": 6,
                "gsrlimit": 50,
                "prop": "imageinfo",
                "iiprop": "url|mime|size",
            }
            try:
                resp = await request_with_retry(
                    client,
                    "GET",
                    self.endpoint,
                    params=params,
                    retries=3,
                    polite_delay=True,
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                pages = (data.get("query") or {}).get("pages") or {}
                for _, page in pages.items():
                    infos = page.get("imageinfo") or []
                    if not infos:
                        continue
                    info = infos[0]
                    url = info.get("url")
                    if isinstance(url, str) and url.startswith("http"):
                        title = page.get("title")
                        source_url = (
                            f"https://commons.wikimedia.org/wiki/{quote(title)}" if isinstance(title, str) else None
                        )
                        candidates.append(
                            Candidate(url=url, provider=self.name, query=q, source_url=source_url)
                        )
            except Exception as exc:  # noqa: BLE001
                failed_logger.append(
                    {
                        "time_kst": now_ts,
                        "provider": self.name,
                        "url": None,
                        "reason": "DOWNLOAD_FAIL",
                        "detail": f"query={q}, error={type(exc).__name__}: {exc}",
                    }
                )
        return candidates
