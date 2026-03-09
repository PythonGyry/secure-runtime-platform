"""Resolve icon paths for bootstrap client (verified.ico) and app icons."""
from __future__ import annotations

import sys
from pathlib import Path


def get_verified_icon_path() -> Path | None:
    """Path to verified.ico for bootstrap windows. None if not found."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates = [base / "icons" / "verified.ico", base / "icons" / "icon.ico", base / "verified.ico"]
    else:
        base = Path(__file__).resolve().parents[2]  # client/
        candidates = [base / "icons" / "verified.ico", base / "icons" / "icon.ico"]
    for p in candidates:
        if p.exists():
            return p
    return None


def get_app_icon_path(runtime_data_dir: Path, app: str) -> Path | None:
    """Path to cached app icon. None if not found."""
    p = runtime_data_dir / "icons" / f"{app}.ico"
    return p if p.exists() else None
