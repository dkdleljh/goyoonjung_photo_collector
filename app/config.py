from __future__ import annotations

from dataclasses import dataclass, field

RELIABLE_DEFAULT_PROVIDERS = ["naver", "wikimedia", "instagram_seed"]
EXPERIMENTAL_PROVIDERS = ["google", "twitter_rss", "twitter_snscrape", "twitter_rsshub"]
ALL_PROVIDERS = [*RELIABLE_DEFAULT_PROVIDERS, *EXPERIMENTAL_PROVIDERS]

# A-mode default: broaden coverage by including google best-effort.
# (May produce more DOWNLOAD_FAIL due to blocking; still useful for discovery.)
DEFAULT_PROVIDERS = [*RELIABLE_DEFAULT_PROVIDERS, "google"]
DEFAULT_KEYWORDS = ["고윤정", "Go Yoonjung", "고윤정 화보", "고윤정 직찍"]


@dataclass
class RunConfig:
    providers: list[str] = field(default_factory=lambda: list(DEFAULT_PROVIDERS))
    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))

    # Downloader
    max_workers: int = 5
    min_short_side_px: int = 720  # default: 720p quality gate

    # Naver
    naver_display: int = 50
    naver_pages: int = 3

    # Google (best-effort)
    google_max_pages: int = 1

    dry_run: bool = False
