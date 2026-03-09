"""
Менеджер платформи: збірка, очищення, адміністрування.

App = назва папки в runtime_logic/apps/ (наприклад wishlist, myapp).
Все передається через аргументи, без хардкоду.

Використання:
  python manager.py list
  python manager.py build -a wishlist -v 1.0.7
  python manager.py build -a app1 -a app2 -v 1.0.0
  python manager.py build --all -v 1.0.8
  python manager.py client -n myapp_bootstrap
  python manager.py full -a wishlist -v 1.0.7
  python manager.py full --all -v 1.0.0 -n bootstrap
  python manager.py admin -p mypassword
  python manager.py db reset
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent


def get_apps_dir() -> Path:
    return PROJECT / "runtime_logic" / "apps"


def list_apps() -> list[str]:
    """Повертає список доступних додатків (папки в runtime_logic/apps/)."""
    apps_dir = get_apps_dir()
    if not apps_dir.exists():
        return []
    return sorted(
        d.name for d in apps_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "src").exists()
    )


def get_db_path() -> Path:
    return PROJECT / "backend" / "data" / "db" / "licenses.db"


def rm(path: Path, project: Path = PROJECT) -> None:
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        try:
            rel = path.relative_to(project)
        except ValueError:
            rel = path
        print(f"  removed: {rel}")


# --- Commands ---

def cmd_list(_args: argparse.Namespace) -> int:
    """Показати доступні програми."""
    apps = list_apps()
    if not apps:
        print("Немає програм. Додайте папку в runtime_logic/apps/<app_id>/")
        return 0
    print("Доступні програми:")
    for app in apps:
        print(f"  - {app}")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Очистити артефакти збірки."""
    full = getattr(args, "full", False)
    print("Cleaning...")

    for d in PROJECT.rglob("__pycache__"):
        if d.is_dir() and "venv" not in str(d) and "site-packages" not in str(d):
            rm(d)

    for pyc in PROJECT.rglob("*.pyc"):
        if pyc.is_file() and "site-packages" not in str(pyc) and "Lib" not in str(pyc):
            rm(pyc)

    rm(PROJECT / "client" / "src" / "security" / "package_unwrap.c")
    rm(PROJECT / "shared" / "crypto" / "runtime_crypto.c")
    # Розширення Cython: .pyd (Windows), .so (Linux)
    for base, patterns in [
        (PROJECT / "client" / "src" / "security", ["package_unwrap.*.pyd", "package_unwrap.*.so"]),
        (PROJECT / "shared" / "crypto", ["runtime_crypto.*.pyd", "runtime_crypto.*.so"]),
    ]:
        if base.exists():
            for pat in patterns:
                for p in base.glob(pat):
                    rm(p)
    rm(PROJECT / "build")
    rm(PROJECT / "dist")
    rm(PROJECT / "client" / "cache")
    rm(PROJECT / ".runtime_data")

    if full:
        db_path = get_db_path()
        if db_path.exists():
            try:
                db_path.unlink()
                print("  deleted database")
            except OSError as e:
                print(f"  could not delete DB (stop backend first): {e}")
                with sqlite3.connect(db_path) as conn:
                    for t in ("runtime_releases", "managed_licenses", "managed_download_tokens", "admin_audit_log", "admin_sessions"):
                        try:
                            conn.execute(f"DELETE FROM {t}")
                            conn.commit()
                            print(f"  cleared {t}")
                        except sqlite3.OperationalError:
                            pass

    rm(PROJECT / "runtime_logic" / "dist")
    rm(PROJECT / "backend" / "packages")

    print("Done.")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """Зібрати runtime-пакети. App = назва папки в runtime_logic/apps/."""
    version = args.version or "1.0.0"
    channel = args.channel or "stable"
    apps = args.app or []

    if args.all:
        apps = list_apps()
        if not apps:
            print("Немає програм. Додайте папку в runtime_logic/apps/<app_id>/")
            return 1

    if not apps:
        available = list_apps()
        if len(available) == 1:
            apps = available
            print(f"Використовую єдину програму: {apps[0]}")
        else:
            print("Вкажіть --app <name> або --all. Доступні:", ", ".join(available) if available else "(немає)")
            return 1

    for app in apps:
        app_dir = get_apps_dir() / app
        if not app_dir.exists() or not (app_dir / "src").exists():
            print(f"Помилка: програма '{app}' не знайдена в runtime_logic/apps/{app}/")
            return 1

    build_script = PROJECT / "runtime_logic" / "build_tools" / "build_runtime_package.py"
    if not build_script.exists():
        print(f"Build script not found: {build_script}")
        return 1

    for app in apps:
        print(f"\nBuilding {app} {version} ({channel})...")
        r = subprocess.run(
            [sys.executable, str(build_script), "--app", app, "--version", version, "--channel", channel],
            cwd=PROJECT,
        )
        if r.returncode != 0:
            print(f"Build failed for {app}")
            return r.returncode

    print(f"\nDone. Packages -> backend/packages/")
    return 0


def _run_cython_build() -> int:
    """Зібрати Cython-розширення: на Windows — через .bat (MSYS2/MinGW), на Linux — gcc."""
    if sys.platform == "win32":
        r = subprocess.run(
            ["cmd", "/c", "client\\build_cython_with_msys2.bat"],
            cwd=PROJECT,
        )
    else:
        r = subprocess.run(
            [sys.executable, str(PROJECT / "client" / "cython_prebuild_cleanup.py")],
            cwd=PROJECT,
        )
        if r.returncode != 0:
            return r.returncode
        r = subprocess.run(
            [sys.executable, "setup_cython_bootstrap.py", "build_ext", "--inplace"],
            cwd=PROJECT,
        )
    return r.returncode


def cmd_client(args: argparse.Namespace) -> int:
    """Зібрати bootstrap exe (Windows) або бінар (Linux). -a app — іконка з apps/<app>/icon.ico, ім'я за замовчуванням {app}_bootstrap."""
    app_raw = getattr(args, "app", None)
    app = app_raw[0] if isinstance(app_raw, list) and app_raw else (app_raw if isinstance(app_raw, str) else None)
    name = getattr(args, "name", None)
    if app and not name:
        exe_name = f"{app}_bootstrap"
    else:
        exe_name = (name or "bootstrap").strip() or "bootstrap"

    print("Building Cython extensions...")
    if _run_cython_build() != 0:
        print("ERROR: Cython build failed. Fix the error above and retry. Build aborted.")
        return 1

    print(f"Building bootstrap {'exe' if sys.platform == 'win32' else 'binary'} ({exe_name})...")
    cmd = [sys.executable, "client/build_client_exe.py", "--name", exe_name]
    if app:
        cmd.extend(["--app", app])
    server_url = getattr(args, "server_url", None)
    if server_url and str(server_url).strip():
        cmd.extend(["--server-url", str(server_url).strip()])
    r = subprocess.run(cmd, cwd=PROJECT)
    if r.returncode != 0:
        return r.returncode

    out_name = f"{exe_name}.exe" if sys.platform == "win32" else exe_name
    print(f"Done. Client -> dist/{out_name}")
    return 0


def cmd_full(args: argparse.Namespace) -> int:
    """Повна перезбірка: clean --full + build + client."""
    args.full = True
    if cmd_clean(args) != 0:
        return 1

    args.all = getattr(args, "all", False)
    args.app = getattr(args, "app", None)
    args.version = getattr(args, "version", None)
    args.channel = getattr(args, "channel", None)
    if cmd_build(args) != 0:
        return 1

    args.name = getattr(args, "client_name", None)
    if not args.name and args.app and len(args.app) == 1:
        args.name = f"{args.app[0]}_bootstrap"
    elif not args.name and args.all and list_apps():
        args.name = f"{list_apps()[0]}_bootstrap"
    elif not args.name:
        args.name = "bootstrap"
    if cmd_client(args) != 0:
        return 1

    return 0


def cmd_admin(args: argparse.Namespace) -> int:
    """Створити або скинути пароль адміна."""
    sys.path.insert(0, str(PROJECT))
    from backend.src.core.settings import BackendSettings
    from backend.src.repositories.admin_repository import AdminRepository
    from backend.src.storage.database import Database

    password = args.password or "admin"
    settings = BackendSettings.load()
    db = Database(settings.db_path)
    repo = AdminRepository(db)

    result = repo.create_or_reset_admin(password, settings.admin_bootstrap_file)
    print("Admin created/updated.")
    print(f"  Username: {result['username']}")
    print(f"  Password: {result['password']}")
    print(f"  Saved to: {settings.admin_bootstrap_file}")
    return 0


def cmd_db(args: argparse.Namespace) -> int:
    """Операції з БД."""
    sub = args.db_action or "reset"
    if sub == "reset":
        db_path = get_db_path()
        if not db_path.exists():
            print("Database does not exist.")
            return 0
        try:
            db_path.unlink()
            print("Database deleted. Will be recreated on next backend start.")
        except OSError as e:
            print(f"Could not delete: {e}. Stop backend first.")
            return 1
    else:
        print(f"Unknown db action: {sub}")
        return 1
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    """Показати статус: програми, пакети, БД."""
    apps = list_apps()
    packages_dir = PROJECT / "backend" / "packages"
    db_path = get_db_path()

    print("Програми (runtime_logic/apps/):")
    for app in apps or ["(немає)"]:
        print(f"  - {app}")

    print("\nПакети (backend/packages/):")
    if packages_dir.exists():
        manifests = list(packages_dir.glob("*.json"))
        if manifests:
            for m in sorted(manifests):
                try:
                    import json
                    d = json.loads(m.read_text(encoding="utf-8"))
                    print(f"  - {d.get('app', '?')} {d.get('channel', '?')} {d.get('version', '?')}")
                except Exception:
                    print(f"  - {m.name}")
        else:
            print("  (порожньо)")
    else:
        print("  (папка не існує)")

    print("\nБД:", "існує" if db_path.exists() else "відсутня")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Запустити backend сервер."""
    env = {**os.environ, "PYTHONPATH": str(PROJECT)}
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "backend.src.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
        cwd=PROJECT,
        env=env,
    )
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    """Зібрати (опціонально) та вигрузити пакети на Linux-сервер. Запускати з Windows (збірка) або будь-де (тільки вигрузка)."""
    deploy_script = PROJECT / "scripts" / "deploy_to_server.py"
    if not deploy_script.exists():
        print(f"Script not found: {deploy_script}", file=sys.stderr)
        return 1
    cmd = [sys.executable, str(deploy_script)]
    if getattr(args, "host", None):
        cmd.extend(["--host", args.host])
    if getattr(args, "user", None):
        cmd.extend(["--user", args.user])
    if getattr(args, "path", None):
        cmd.extend(["--path", args.path])
    if getattr(args, "key", None):
        cmd.extend(["--key", args.key])
    if getattr(args, "password", None):
        cmd.extend(["--password", args.password])
    if getattr(args, "build", False):
        cmd.append("--build")
    if getattr(args, "build_client", False):
        cmd.append("--build-client")
    if getattr(args, "server_url", None):
        cmd.extend(["--server-url", args.server_url])
    if getattr(args, "app", None):
        cmd.extend(["--app", args.app])
    if getattr(args, "version", None):
        cmd.extend(["--version", args.version])
    if getattr(args, "client_name", None):
        cmd.extend(["--client-name", args.client_name])
    if getattr(args, "dry_run", False):
        cmd.append("--dry-run")
    r = subprocess.run(cmd, cwd=PROJECT)
    return r.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Менеджер платформи: збірка, очистка, адміністрування (app = назва папки в runtime_logic/apps/)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Команда")

    # list
    p_list = subparsers.add_parser("list", help="Показати доступні програми")
    p_list.set_defaults(func=cmd_list)

    # status
    p_status = subparsers.add_parser("status", help="Статус: програми, пакети, БД")
    p_status.set_defaults(func=cmd_status)

    # clean
    p_clean = subparsers.add_parser("clean", help="Очистити артефакти збірки")
    p_clean.add_argument("--full", action="store_true", help="Повна очистка + скинути БД")
    p_clean.set_defaults(func=cmd_clean)

    # build
    p_build = subparsers.add_parser("build", help="Зібрати runtime-пакети (app = назва папки в runtime_logic/apps/)")
    p_build.add_argument("--app", "-a", action="append", help="Додаток за назвою папки (можна кілька)")
    p_build.add_argument("--all", action="store_true", help="Зібрати всі програми")
    p_build.add_argument("--version", "-v", help="Версія (default: 1.0.0)")
    p_build.add_argument("--channel", "-c", help="Канал (default: stable)")
    p_build.set_defaults(func=cmd_build)

    # client
    p_client = subparsers.add_parser("client", help="Зібрати bootstrap exe (Windows) або бінар (Linux)")
    p_client.add_argument("--app", "-a", help="Апка (напр. wishlist) — іконка з apps/<app>/icon.ico, ім'я: <app>_bootstrap")
    p_client.add_argument("--name", "-n", help="Ім'я exe (override). Напр. 'NBU Coins Monitor'")
    p_client.add_argument("--server-url", "-s", help="URL сервера для клієнта (вшивається в exe — для підключення до Linux-сервера)")
    p_client.set_defaults(func=cmd_client)

    # full
    p_full = subparsers.add_parser("full", help="Повна перезбірка: clean + build + client")
    p_full.add_argument("--app", "-a", action="append", help="Додаток за назвою папки")
    p_full.add_argument("--all", action="store_true", help="Зібрати всі програми")
    p_full.add_argument("--version", "-v", help="Версія (default: 1.0.0)")
    p_full.add_argument("--channel", "-c", help="Канал (default: stable)")
    p_full.add_argument("--client-name", "-n", help="Ім'я exe клієнта. Якщо -a без -n: <app>_bootstrap")
    p_full.set_defaults(func=cmd_full)

    # admin
    p_admin = subparsers.add_parser("admin", help="Створити/скинути адміна")
    p_admin.add_argument("--password", "-p", default="admin", help="Пароль (default: admin)")
    p_admin.set_defaults(func=cmd_admin)

    # db
    p_db = subparsers.add_parser("db", help="Операції з БД")
    p_db.add_argument("db_action", nargs="?", choices=["reset"], default="reset", help="reset - видалити БД")
    p_db.set_defaults(func=cmd_db)

    # run
    p_run = subparsers.add_parser("run", help="Запустити backend сервер")
    p_run.set_defaults(func=cmd_run)

    # deploy (збірка на Windows + вигрузка пакетів на Linux)
    p_deploy = subparsers.add_parser("deploy", help="Вигрузити пакети на Linux-сервер (опціонально: спочатку зібрати та зібрати exe)")
    p_deploy.add_argument("--host", "-H", help="Хост сервера")
    p_deploy.add_argument("--user", "-u", help="SSH користувач")
    p_deploy.add_argument("--path", "-p", help="Шлях до проекту на сервері")
    p_deploy.add_argument("--key", "-k", help="Шлях до SSH-ключа")
    p_deploy.add_argument("--password", help="Пароль SSH (краще DEPLOY_PASSWORD)")
    p_deploy.add_argument("--build", "-b", action="store_true", help="Спочатку зібрати пакети (manager build)")
    p_deploy.add_argument("--build-client", action="store_true", help="Зібрати .exe з --server-url")
    p_deploy.add_argument("--server-url", "-s", help="URL сервера для клієнта (напр. https://your-server.com)")
    p_deploy.add_argument("--app", "-a", default="wishlist", help="App для build/build-client")
    p_deploy.add_argument("--version", "-v", default="1.0.0", help="Версія для build")
    p_deploy.add_argument("--client-name", "-n", help="Ім'я exe клієнта")
    p_deploy.add_argument("--dry-run", action="store_true", help="Тільки показати дії")
    p_deploy.set_defaults(func=cmd_deploy)

    parsed = parser.parse_args()
    if not parsed.command:
        parser.print_help()
        return 0

    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
