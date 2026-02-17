from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class OrganizeResult:
    width: int
    height: int
    size_bytes: int
    targets: list[str]


def classify(width: int, height: int, size_bytes: int) -> list[str]:
    """Return subpaths (relative to photo_root) to copy the image into."""
    targets: list[str] = []

    # Best Cuts (Ultra HD)
    if width >= 3000 or size_bytes >= 2 * 1024 * 1024:
        targets.append("Organized/Best_Cuts")

    # Wallpapers / HQ buckets
    if max(width, height) >= 1920:
        if height > width:
            targets.append("Organized/Mobile_Wallpapers")
        else:
            targets.append("Organized/Desktop_Wallpapers")
    elif max(width, height) >= 1000:
        targets.append("Organized/General_HQ")
    else:
        targets.append("Organized/Archive_LowRes")

    return targets


def inspect_image(path: Path) -> OrganizeResult:
    with Image.open(path) as img:
        width, height = img.size
    size_bytes = path.stat().st_size
    targets = classify(width, height, size_bytes)
    return OrganizeResult(width=width, height=height, size_bytes=size_bytes, targets=targets)
