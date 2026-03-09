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
    fixed_app: str  # Якщо не порожньо — клієнт зібрано з -a <app>, завантажувати тільки цю апку

    @classmethod
    def load(cls) -> "BootstrapSettings":
        root_dir = _get_root_dir()
        data_dir = root_dir / ".runtime_data"
        data_dir.mkdir(parents=True, exist_ok=True)

        legacy_dir = root_dir.parent / "version_3_tkinter"

        default_server = "http://127.0.0.1:8000"
        fixed_app = ""
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                meipass_path = Path(meipass)
                bundle_url_file = meipass_path / "bundle_server_url.txt"
                if bundle_url_file.exists():
                    try:
                        default_server = bundle_url_file.read_text(encoding="utf-8").strip() or default_server
                    except Exception:
                        pass
                bundle_app_file = meipass_path / "bundle_app.txt"
                if bundle_app_file.exists():
                    try:
                        fixed_app = bundle_app_file.read_text(encoding="utf-8").strip() or ""
                    except Exception:
                        pass

        return cls(
            state_db_path=data_dir / "bootstrap_state.db",
            legacy_base_dir=legacy_dir,
            runtime_data_dir=data_dir,
            default_server_base_url=default_server,
            default_channel="stable",
            fixed_app=fixed_app,
        )
