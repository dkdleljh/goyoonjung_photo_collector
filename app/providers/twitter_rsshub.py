from __future__ import annotations

import logging
import os
import re
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from app.models import Candidate

LOGGER = logging.getLogger(__name__)


def _normalize_media_url(url: str) -> str:
    if not url:
        return ""
    if "name=" in url:
        return re.sub(r"name=[\w]+", "name=orig", url)
    if "?" not in url:
        return url + "?name=orig"
    return url + "&name=orig"


class TwitterRSSHubProvider:
    """Twitter keyword search via RSSHub.

    Requires a reachable RSSHub instance (self-hosted recommended).

    Env:
      - RSSHUB_BASE_URL (default: http://127.0.0.1:1200)

    Notes:
      - Twitter routes on RSSHub typically require auth configuration on the RSSHub side.
      - This provider only parses RSS XML and extracts pbs.twimg.com images from item descriptions.
    """

    name = "twitter_rsshub"
    experimental = True

    def __init__(self, keywords: list[str] | None = None, limit_per_keyword: int = 20):
        self.keywords = keywords or ["고윤정", "Go Yoonjung", "고윤정 직찍"]
        self.limit_per_keyword = int(limit_per_keyword)
        self.base = (os.getenv("RSSHUB_BASE_URL") or "http://127.0.0.1:1200").rstrip("/")

    async def collect(self, client, failed_logger, now_ts: str):
        candidates: list[Candidate] = []

        for kw in self.keywords:
            url = f"{self.base}/twitter/keyword/{kw}"
            try:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code != 200:
                    LOGGER.warning("RSSHub twitter keyword failed: status=%s url=%s", resp.status_code, url)
                    try:
                        failed_logger.append(
                            {
                                "time_kst": now_ts,
                                "provider": self.name,
                                "url": url,
                                "reason": "RSSHUB_HTTP",
                                "detail": f"status={resp.status_code}",
                            }
                        )
                    except Exception:
                        pass
                    continue

                root = ElementTree.fromstring(resp.content)
                items = root.findall(".//item")[: self.limit_per_keyword]
                for item in items:
                    desc = item.findtext("description") or ""
                    link = item.findtext("link") or ""
                    if not desc:
                        continue
                    soup = BeautifulSoup(desc, "lxml")
                    for img in soup.find_all("img"):
                        src = img.get("src") or ""
                        if "pbs.twimg.com" not in src:
                            continue
                        src = _normalize_media_url(src)
                        candidates.append(Candidate(url=src, provider=self.name, source_url=link, query=kw))
            except Exception as exc:
                LOGGER.warning("RSSHub twitter error (%s): %s", kw, exc)
                try:
                    failed_logger.append(
                        {
                            "time_kst": now_ts,
                            "provider": self.name,
                            "url": url,
                            "reason": "RSSHUB_EXCEPTION",
                            "detail": f"{kw}: {type(exc).__name__}: {exc}",
                        }
                    )
                except Exception:
                    pass

        LOGGER.info("RSSHub twitter collected %s candidates", len(candidates))
        return candidates
