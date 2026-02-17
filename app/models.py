from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Candidate:
    url: str
    provider: str
    query: str | None = None
    source_url: str | None = None


@dataclass(slots=True)
class DownloadOutcome:
    ok: bool
    reason: str
    provider: str
    url: str
    saved_path: str | None = None
