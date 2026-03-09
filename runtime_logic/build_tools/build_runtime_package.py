from __future__ import annotations

import argparse
import compileall
import json
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.crypto.runtime_crypto import sha256_bytes
from backend.src.storage.database import Database
from backend.src.repositories.package_repository import PackageRepository

CACHE_TAG = sys.implementation.cache_tag


def build_package(app: str, version: str, channel: str) -> None:
    project_root = PROJECT_ROOT
    app_dir = project_root / "runtime_logic" / "apps" / app
    if not app_dir.exists():
        raise FileNotFoundError(f"App not found: {app} (expected {app_dir})")
    source_root = app_dir / "src"
    shared_root = project_root / "shared"
    dist_root = project_root / "runtime_logic" / "dist"
    backend_packages = project_root / "backend" / "packages"

    dist_root.mkdir(parents=True, exist_ok=True)
    backend_packages.mkdir(parents=True, exist_ok=True)

    archive_name = f"runtime_{app}_{channel}_{version}.zip"
    archive_path = dist_root / archive_name

    compileall.compile_dir(source_root, force=True, quiet=1, legacy=True)
    compileall.compile_dir(shared_root, force=True, quiet=1, legacy=True)

    init_content = b""
    package_dirs = set()
    for root in (source_root, shared_root):
        for py_path in root.rglob("*.py"):
            parent = py_path.parent
            rel = parent.relative_to(project_root)
            for i in range(len(rel.parts)):
                package_dirs.add(project_root / Path(*rel.parts[: i + 1]))

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for pkg_dir in sorted(package_dirs):
            init_py = pkg_dir / "__init__.py"
            arcname = str(pkg_dir.relative_to(project_root) / "__init__.py")
            if init_py.exists():
                archive.write(init_py, arcname)
            else:
                archive.writestr(arcname, init_content)
        for root in (source_root, shared_root):
            for py_path in root.rglob("*.py"):
                mod_name = py_path.stem
                for pyc_name in (f"{mod_name}.{CACHE_TAG}.pyc", f"{mod_name}.pyc"):
                    pyc_path = py_path.parent / pyc_name
                    if pyc_path.exists():
                        arcname = str(pyc_path.relative_to(project_root))
                        archive.write(pyc_path, arcname)
                        pyc_path.unlink(missing_ok=True)
                        break

    package_bytes = archive_path.read_bytes()
    module_name = f"runtime_logic.apps.{app}.src.entrypoints.runtime_entry"
    manifest = {
        "app": app,
        "version": version,
        "channel": channel,
        "module_name": module_name,
        "entrypoint": "run_runtime",
        "package_file": archive_name,
        "package_sha256": sha256_bytes(package_bytes),
        "package_size": len(package_bytes),
    }

    manifest_filename = f"{app}_{channel}_{version}.json"
    manifest_path = dist_root / manifest_filename
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    (backend_packages / archive_name).write_bytes(package_bytes)
    (backend_packages / manifest_filename).write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")

    icons_dir = backend_packages / "icons"
    icons_dir.mkdir(exist_ok=True)
    app_icon = app_dir / "icon.ico"
    if app_icon.exists():
        (icons_dir / f"{app}.ico").write_bytes(app_icon.read_bytes())

    db_path = project_root / "backend" / "data" / "db" / "licenses.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database = Database(db_path)
    repository = PackageRepository(database, backend_packages)
    repository.upsert_release(
        app=app,
        channel=channel,
        version=version,
        module_name=manifest["module_name"],
        entrypoint=manifest["entrypoint"],
        package_file=archive_name,
        package_path=str(backend_packages / archive_name),
        manifest_path=str(backend_packages / manifest_filename),
        package_sha256=manifest["package_sha256"],
        package_size=manifest["package_size"],
        status="published",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build runtime package (app = folder name in runtime_logic/apps/)")
    parser.add_argument("--app", "-a", required=True, help="App id = folder name in runtime_logic/apps/")
    parser.add_argument("--version", "-v", required=True, help="Version")
    parser.add_argument("--channel", "-c", default="stable", help="Channel (default: stable)")
    args = parser.parse_args()
    build_package(args.app, args.version, args.channel)


if __name__ == "__main__":
    main()
