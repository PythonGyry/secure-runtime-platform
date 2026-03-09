from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class BackendSettings:
    host: str
    port: int
    data_dir: Path
    db_path: Path
    packages_dir: Path
    backups_dir: Path
    keypair_file: Path
    admin_bootstrap_file: Path

    @classmethod
    def load(cls) -> "BackendSettings":
        root_dir = Path(__file__).resolve().parents[2]
        data_dir = root_dir / "data"
        packages_dir = root_dir / "packages"
        backups_dir = data_dir / "backups"
        db_dir = data_dir / "db"
        keypair_file = data_dir / "signing_keypair.json"
        admin_bootstrap_file = data_dir / "admin_bootstrap.json"

        data_dir.mkdir(parents=True, exist_ok=True)
        packages_dir.mkdir(parents=True, exist_ok=True)
        backups_dir.mkdir(parents=True, exist_ok=True)
        db_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            host="127.0.0.1",
            port=8000,
            data_dir=data_dir,
            db_path=db_dir / "licenses.db",
            packages_dir=packages_dir,
            backups_dir=backups_dir,
            keypair_file=keypair_file,
            admin_bootstrap_file=admin_bootstrap_file,
        )
