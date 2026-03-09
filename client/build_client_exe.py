"""
Збірка bootstrap exe. Ім'я передається аргументом (модульно для багатьох програм).

  python client/build_client_exe.py --name myapp_bootstrap
  python client/build_client_exe.py -n wishlist_bootstrap
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Збірка bootstrap exe")
    parser.add_argument("--name", "-n", default="bootstrap", help="Ім'я exe без .exe")
    parser.add_argument("--app", "-a", help="Апка — іконка з runtime_logic/apps/<app>/icon.ico")
    parser.add_argument("--server-url", "-s", help="URL сервера для клієнта (вшивається в exe, напр. https://my.server.com)")
    args = parser.parse_args()
    exe_name = (args.name or "bootstrap").strip() or "bootstrap"

    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "client" / "build_config.py"
    app = getattr(args, "app", None) or ""
    config_path.write_text(
        f'"""Автогенеровано build_client_exe.py"""\nexe_name = {exe_name!r}\napp = {app!r}\n',
        encoding="utf-8",
    )

    # URL сервера для зібраного exe (опціонально) — читається в bootstrap_settings при frozen
    server_url = getattr(args, "server_url", None) or ""
    bundle_url_file = project_root / "client" / "bundle_server_url.txt"
    if server_url and server_url.strip():
        bundle_url_file.write_text(server_url.strip(), encoding="utf-8")
    elif bundle_url_file.exists():
        bundle_url_file.unlink()

    # Фіксована апка для exe: при -a <app> клієнт завантажує тільки цю апку (без меню вибору)
    bundle_app_file = project_root / "client" / "bundle_app.txt"
    if app and app.strip():
        bundle_app_file.write_text(app.strip(), encoding="utf-8")
    elif bundle_app_file.exists():
        bundle_app_file.unlink()

    # Видалення старих Cython-розширень (.pyd / .so) перед збіркою
    r_clean = subprocess.run(
        [sys.executable, str(project_root / "client" / "cython_prebuild_cleanup.py")],
        cwd=project_root,
    )
    if r_clean.returncode != 0:
        return 1

    result = subprocess.run(
        [sys.executable, "setup_cython_bootstrap.py", "build_ext", "--inplace"],
        cwd=project_root,
    )
    if result.returncode != 0:
        print("ERROR: Cython build failed. Fix the error above. Build aborted.")
        return 1

    # Іконка з apps/<app>/icon.ico → client/icons/verified.ico
    ensure_cmd = [sys.executable, str(project_root / "client" / "ensure_exe_icon.py")]
    if getattr(args, "app", None):
        ensure_cmd.extend(["--app", args.app])
    r = subprocess.run(ensure_cmd, cwd=project_root)
    if r.returncode != 0:
        print("ERROR: ensure_exe_icon failed. Build aborted.")
        return 1

    # Шлях до іконки для spec (тільки якщо -a передано)
    icon_path_file = project_root / "client" / "build_icon.txt"
    if app:
        app_icon = project_root / "runtime_logic" / "apps" / app / "icon.ico"
        if app_icon.exists():
            icon_path_file.write_text(str(app_icon.resolve()), encoding="utf-8")
        else:
            icon_path_file.write_text("", encoding="utf-8")
    else:
        icon_path_file.write_text("", encoding="utf-8")

    spec_path = project_root / "client" / "bootstrap_client.spec"
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(spec_path)],
        cwd=project_root,
    )
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
