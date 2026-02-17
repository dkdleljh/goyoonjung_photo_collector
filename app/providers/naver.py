from __future__ import annotations

import os
from typing import Any

import httpx

from app.http_utils import request_with_retry
from app.models import Candidate


class NaverImageProvider:
    name = "naver"
    endpoint = "https://openapi.naver.com/v1/search/image"

    def __init__(self, display: int = 100, pages: int = 5) -> None:
        self.display = display
        self.pages = pages

    async def collect(
        self,
        client: httpx.AsyncClient,
        keywords: list[str],
        failed_logger,
        now_ts: str,
    ) -> list[Candidate]:
        client_id = os.getenv("NAVER_CLIENT_ID")
        client_secret = os.getenv("NAVER_CLIENT_SECRET")

        if not client_id or not client_secret:
            failed_logger.append(
                {
                    "time_kst": now_ts,
                    "provider": self.name,
                    "url": None,
                    "reason": "MISSING_NAVER_KEYS",
                    "detail": "NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 누락",
                }
            )
            return []

        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }

        candidates: list[Candidate] = []
        for kw in keywords:
            for page in range(self.pages):
                start = page * self.display + 1
                params = {"query": kw, "display": self.display, "start": start, "sort": "sim"}
                try:
                    resp = await request_with_retry(
                        client,
                        "GET",
                        self.endpoint,
                        headers=headers,
                        params=params,
                        retries=3,
                        polite_delay=True,
                    )
                    resp.raise_for_status()
                    data: dict[str, Any] = resp.json()
                    items = data.get("items", [])
                    for item in items:
                        link = item.get("link")
                        if isinstance(link, str) and link.startswith("http"):
                            candidates.append(Candidate(url=link, provider=self.name, query=kw))
                except Exception as exc:  # noqa: BLE001
                    failed_logger.append(
                        {
                            "time_kst": now_ts,
                            "provider": self.name,
                            "url": None,
                            "reason": "DOWNLOAD_FAIL",
                            "detail": f"query={kw}, start={start}, error={type(exc).__name__}: {exc}",
                        }
                    )
        return candidates
