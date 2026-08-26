from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "RussianOrthodoxCalendar"


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def user_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / APP_NAME


def ensure_user_dirs() -> dict[str, Path]:
    root = user_root()
    paths = {name: root / name for name in ("database", "cache", "logs", "config", "output", "imports")}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def asset_path(*parts: str) -> Path:
    return resource_root().joinpath("assets", *parts)

