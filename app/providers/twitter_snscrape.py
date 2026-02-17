from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.models import Candidate

LOGGER = logging.getLogger(__name__)


@dataclass
class _TweetResult:
    url: str
    media_urls: list[str]


def _normalize_media_url(url: str) -> str:
    """pbs.twimg.com 이미지 URL을 가능한 원본(name=orig)으로 정규화."""
    if not isinstance(url, str) or not url:
        return ""
    # 이미 name 파라미터가 있으면 orig로
    if "name=" in url:
        return re.sub(r"name=[\w]+", "name=orig", url)
    # 쿼리가 없으면 name=orig 추가
    if "?" not in url:
        return url + "?name=orig"
    return url + "&name=orig"


class TwitterSnScrapeProvider:
    """Twitter/X keyword search via snscrape.

    장점: Nitter처럼 RSS 인스턴스 의존이 없음.
    단점: 트위터 측 차단/구조 변경에 따라 snscrape가 깨질 수 있음.
    """

    name = "twitter_snscrape"
    experimental = True

    def __init__(
        self,
        keywords: list[str] | None = None,
        limit_per_keyword: int = 30,
    ):
        self.keywords = keywords or ["고윤정", "Go Yoonjung", "고윤정 직찍"]
        self.limit_per_keyword = int(limit_per_keyword)

    async def collect(self, client, failed_logger, now_ts: str):  # noqa: ARG002
        # snscrape는 sync 라이브러리라 async 클라이언트를 쓰지 않습니다.
        try:
            import snscrape.modules.twitter as sntwitter
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("snscrape import failed: %s", exc)
            return []

        candidates: list[Candidate] = []

        for kw in self.keywords:
            query = f"{kw} filter:images"
            try:
                scraper = sntwitter.TwitterSearchScraper(query)
                n = 0
                for tweet in scraper.get_items():
                    # tweet.media는 Photo/Video/Gif 등
                    media = getattr(tweet, "media", None) or []
                    for m in media:
                        # Photo는 .fullUrl 또는 .url 가 있음(버전에 따라 다름)
                        full = getattr(m, "fullUrl", None) or getattr(m, "url", None)
                        if not full:
                            continue
                        full = str(full)
                        if "pbs.twimg.com" not in full:
                            continue
                        img = _normalize_media_url(full)
                        if not img:
                            continue
                        candidates.append(
                            Candidate(
                                url=img,
                                provider=self.name,
                                source_url=str(getattr(tweet, "url", "")),
                                query=kw,
                            )
                        )
                    n += 1
                    if n >= self.limit_per_keyword:
                        break
            except Exception as exc:
                # collector 전체를 망치지 않도록 실패는 로깅만
                LOGGER.warning("Twitter snscrape error (%s): %s", kw, exc)
                try:
                    failed_logger.append(
                        {
                            "time_kst": now_ts,
                            "provider": self.name,
                            "url": None,
                            "reason": "TWITTER_SNSCRAPE_ERROR",
                            "detail": f"{kw}: {type(exc).__name__}: {exc}",
                        }
                    )
                except Exception:
                    pass

        LOGGER.info("Twitter snscrape collected %s candidates", len(candidates))
        return candidates
