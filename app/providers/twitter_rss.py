import asyncio
import re
import random
import logging
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from app.models import Candidate

LOGGER = logging.getLogger(__name__)

class TwitterRSSProvider:
    name = "twitter_rss"
    experimental = True

    def __init__(self):
        # Nitter 인스턴스 리스트 (트위터 우회 접속)
        # 차단될 경우를 대비해 여러 개를 로테이션
        self.instances = [
            "https://nitter.net",
            "https://nitter.cz",
            "https://nitter.privacydev.net",
            "https://nitter.projectsegfau.lt",
        ]
        self.keywords = ["고윤정", "Go Yoonjung", "고윤정 직찍"]

    async def collect(self, client: httpx.AsyncClient, failed_logger, now_ts: str) -> list[Candidate]:
        candidates = []
        
        # 랜덤 인스턴스 선택 (부하 분산)
        instance = random.choice(self.instances)
        
        for kw in self.keywords:
            # RSS URL 생성 (검색어 기반)
            rss_url = f"{instance}/search/rss?f=tweets&q={kw}"
            
            try:
                # 약간의 딜레이
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                resp = await client.get(
                    rss_url,
                    follow_redirects=True,
                    headers={
                        # 간단한 UA/Accept로 일부 인스턴스의 과한 차단을 완화
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                        "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
                if resp.status_code != 200:
                    LOGGER.warning(f"Twitter RSS fetch failed: status={resp.status_code} url={rss_url}")
                    continue

                # Nitter는 Cloudflare/차단으로 HTML(검증페이지) 또는 빈 응답을 주는 경우가 많습니다.
                # XML이 아닐 때는 파싱 예외를 내지 않고 조용히 스킵합니다.
                content = resp.content or b""
                ct = (resp.headers.get("content-type") or "").lower()
                head = content[:200].lstrip()
                looks_xml = head.startswith(b"<?xml") or head.startswith(b"<rss") or b"<rss" in head[:200]
                if ("xml" not in ct) and (not looks_xml):
                    sample = resp.text[:120].replace("\n", " ") if resp.text else ""
                    LOGGER.warning(f"Twitter RSS blocked/non-XML. instance={instance} kw={kw} ct={ct or 'n/a'} sample={sample}")
                    continue

                # XML 파싱
                root = ElementTree.fromstring(content)
                
                # RSS 아이템 순회
                for item in root.findall(".//item"):
                    description = item.find("description").text if item.find("description") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else ""
                    
                    if not description:
                        continue

                    # HTML 내용에서 이미지 URL 추출
                    soup = BeautifulSoup(description, "lxml")
                    imgs = soup.find_all("img")
                    
                    for img in imgs:
                        src = img.get("src")
                        if not src:
                            continue
                        
                        # Nitter 프록시 URL을 원본 트위터 URL 형식으로 변환 시도 (선택적)
                        # 여기서는 Nitter가 제공하는 URL을 그대로 쓰되, 고화질 처리
                        # 트위터 이미지는 보통 name=small 등의 파라미터가 붙음 -> name=orig로 변경하면 원본
                        
                        # 예: https://nitter.net/pic/media%2F...jpg%3Fname%3Dsmall
                        # 디코딩 및 파라미터 교체
                        
                        if "name=" in src:
                            src = re.sub(r"name=[\w]+", "name=orig", src)
                        elif "?" not in src:
                            src += "?name=orig"
                            
                        # 중복 방지용 쿼리 제거한 URL (Candidate용)
                        candidates.append(Candidate(
                            url=src,
                            provider=self.name,
                            source_url=link,
                            query=kw
                        ))

            except Exception as e:
                LOGGER.warning(f"Twitter RSS Error ({kw}): {e}")
                
        LOGGER.info(f"Twitter RSS collected {len(candidates)} candidates")
        return candidates
