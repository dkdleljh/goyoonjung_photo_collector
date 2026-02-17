#!/usr/bin/env python3
"""Reorganize existing downloaded images.

- Uses the same classification rules as the downloader (`app.organize`).
- Scans the photo root (`Desktop/Goyoonjung_Photos` or `${PHOTO_ROOT}/Goyoonjung_Photos`).
- Skips files already inside `Organized/`.

This script is safe to run repeatedly.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.organize import inspect_image
from app.paths import get_photo_root


def is_image(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}


def main() -> int:
    root = get_photo_root()
    organized = root / "Organized"

    processed = 0
    copied = 0

    for dirpath, _dirs, files in os.walk(root):
        p = Path(dirpath)
        if organized in p.parents or p == organized:
            continue

        for name in files:
            fp = p / name
            if not fp.is_file() or not is_image(fp):
                continue

            processed += 1
            try:
                info = inspect_image(fp)
            except Exception:
                continue

            for sub in info.targets:
                dest_dir = root / sub
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / fp.name
                if dest_path.exists():
                    continue
                shutil.copy2(fp, dest_path)
                copied += 1

    print(f"[reorganize] root={root}")
    print(f"[reorganize] processed_files={processed}")
    print(f"[reorganize] copied_files={copied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
