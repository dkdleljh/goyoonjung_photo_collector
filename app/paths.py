from __future__ import annotations

import os
import platform
from pathlib import Path


def _expand(path_str: str) -> Path:
    return Path(path_str.replace("$HOME", str(Path.home())).replace('"', "")).expanduser()


def _read_xdg_desktop_dir() -> Path | None:
    env_dir = os.getenv("XDG_DESKTOP_DIR")
    if env_dir:
        return _expand(env_dir)

    user_dirs = Path.home() / ".config" / "user-dirs.dirs"
    if not user_dirs.exists():
        return None

    try:
        for line in user_dirs.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("XDG_DESKTOP_DIR="):
                value = line.split("=", 1)[1].strip()
                return _expand(value)
    except OSError:
        return None
    return None


def is_chromeos() -> bool:
    if "chromeos" in platform.platform().lower() or "chromeos" in platform.release().lower():
        return True

    lsb_release = Path("/etc/lsb-release")
    if lsb_release.exists():
        try:
            return "CHROMEOS" in lsb_release.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
    return False


def detect_desktop_base() -> Path:
    photo_root = os.getenv("PHOTO_ROOT")
    if photo_root:
        return Path(photo_root).expanduser().resolve()

    system = platform.system().lower()
    home = Path.home()

    if system == "windows":
        userprofile = os.getenv("USERPROFILE")
        candidates: list[Path] = []
        if userprofile:
            base = Path(userprofile)
            candidates.append(base / "Desktop")
            candidates.append(base / "OneDrive" / "Desktop")
        candidates.append(home / "Desktop")

        for p in candidates:
            if p.exists():
                return p.resolve()
        return (home / "Desktop").resolve()

    if system == "darwin":
        return (home / "Desktop").resolve()

    xdg = _read_xdg_desktop_dir()
    if xdg is not None:
        return xdg.resolve()

    return (home / "Desktop").resolve()


def get_photo_root() -> Path:
    if is_chromeos():
        raise RuntimeError("ChromeOS는 지원하지 않습니다.")

    desktop = detect_desktop_base()
    root = desktop / "Goyoonjung_Photos"
    root.mkdir(parents=True, exist_ok=True)
    return root
