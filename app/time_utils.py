from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(tz=KST)


def kst_date_str() -> str:
    return now_kst().strftime("%Y-%m-%d")


def kst_timestamp_str() -> str:
    return now_kst().isoformat()
