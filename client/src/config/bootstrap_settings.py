from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


def _get_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class BootstrapSettings:
    state_db_path: Path
    legacy_base_dir: Path
    runtime_data_dir: Path
    default_server_base_url: str
    default_channel: str

    @classmethod
    def load(cls) -> "BootstrapSettings":
        root_dir = _get_root_dir()
        data_dir = root_dir / ".runtime_data"
        data_dir.mkdir(parents=True, exist_ok=True)

        legacy_dir = root_dir.parent / "version_3_tkinter"

        return cls(
            state_db_path=data_dir / "bootstrap_state.db",
            legacy_base_dir=legacy_dir,
            runtime_data_dir=data_dir,
            default_server_base_url="http://127.0.0.1:8000",
            default_channel="stable",
        )
