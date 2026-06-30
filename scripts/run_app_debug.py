"""
Універсальний запуск будь-якої апки з runtime_logic/apps у debug-режимі:
логи в консоль, дані в локальній папці .dev_data апки.

Використання (з кореня проєкту):
  python scripts/run_app_debug.py wishlist
  python scripts/run_app_debug.py -a wishlist
  python scripts/run_app_debug.py wishlist --data-dir .dev_data_b

Другий екземпляр з окремою БД (паралельно в іншому терміналі):
  python scripts/run_app_debug.py wishlist --data-dir .dev_data_b

Або через змінну середовища:
  set WISHLIST_DATA_DIR=C:/path/to/my_data
  python scripts/run_app_debug.py wishlist

Список доступних апок:
  python scripts/run_app_debug.py --list
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

# Корінь проєкту
PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


def get_apps_dir() -> Path:
    return PROJECT / "runtime_logic" / "apps"


def list_app_ids() -> list[str]:
    apps_dir = get_apps_dir()
    if not apps_dir.exists():
        return []
    return sorted(
        d.name for d in apps_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "src").exists()
    )


def resolve_data_dir(app_id: str, data_dir: str | Path | None) -> Path:
    """Каталог даних: акаунти, wishlist_secure.db, legacy."""
    if data_dir is None or (isinstance(data_dir, str) and not str(data_dir).strip()):
        env = os.environ.get("WISHLIST_DATA_DIR", "").strip()
        if env:
            data_dir = env
        else:
            return (get_apps_dir() / app_id / ".dev_data").resolve()
    path = Path(data_dir)
    if not path.is_absolute():
        path = (get_apps_dir() / app_id / path).resolve()
    else:
        path = path.resolve()
    return path


def build_debug_context(app_id: str, *, data_dir: str | Path | None = None) -> dict:
    """Мінімальний context_payload для запуску апки в debug."""
    dev_data = resolve_data_dir(app_id, data_dir)
    dev_data.mkdir(parents=True, exist_ok=True)
    legacy_dir = dev_data / "legacy"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    server_url = os.environ.get("RUNTIME_SERVER_URL", "https://secure-runtime-platform.duckdns.org")
    return {
        "license_key": "dev-debug-key",
        "hwid": "dev-machine",
        "server_base_url": server_url,
        "server_salt": "dev-salt",
        "runtime_data_dir": str(dev_data),
        "legacy_base_dir": str(legacy_dir),
        "icon_path": None,
        "app_version": "dev",
        "debug": True,
    }


def run_app_debug(app_id: str, *, data_dir: str | Path | None = None) -> int:
    apps_dir = get_apps_dir()
    app_dir = apps_dir / app_id
    if not app_dir.is_dir():
        print(f"Помилка: апка '{app_id}' не знайдена (очікувалась папка {app_dir})", file=sys.stderr)
        return 1
    if not (app_dir / "src").exists():
        print(f"Помилка: у апки '{app_id}' немає папки src/", file=sys.stderr)
        return 1

    module_name = f"runtime_logic.apps.{app_id}.src.entrypoints.runtime_entry"
    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        print(f"Помилка імпорту {module_name}: {e}", file=sys.stderr)
        return 1

    run_runtime = getattr(mod, "run_runtime", None)
    if not callable(run_runtime):
        print(f"Помилка: у модулі {module_name} немає функції run_runtime", file=sys.stderr)
        return 1

    context_payload = build_debug_context(app_id, data_dir=data_dir)
    if os.environ.get("RUNTIME_DEBUG", "").strip().lower() in ("1", "true", "yes"):
        context_payload["debug"] = True

    db_path = Path(context_payload["runtime_data_dir"]) / "wishlist_secure.db"
    print(f"[debug] app={app_id}")
    print(f"[debug] data_dir={context_payload['runtime_data_dir']}")
    print(f"[debug] db={db_path}")

    run_runtime(context_payload)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Запуск апки з runtime_logic/apps у debug-режимі (логи в консоль)",
    )
    parser.add_argument(
        "app",
        nargs="?",
        help="ID апки (назва папки в runtime_logic/apps/, напр. wishlist)",
    )
    parser.add_argument("-a", "--app-id", dest="app_id", help="Те саме, що позиційний app")
    parser.add_argument("-l", "--list", action="store_true", help="Показати список доступних апок")
    parser.add_argument(
        "--data-dir",
        dest="data_dir",
        metavar="PATH",
        help="Окремий каталог даних (БД wishlist_secure.db). Відносний шлях — від runtime_logic/apps/<app>/",
    )
    args = parser.parse_args()

    if args.list:
        apps = list_app_ids()
        if not apps:
            print("Немає апок. Додай папку в runtime_logic/apps/<app_id>/ з підпапкою src/")
        else:
            print("Доступні апки:")
            for a in apps:
                print(f"  - {a}")
        return 0

    app_id = args.app_id or args.app
    if not app_id:
        parser.error("Вкажи ID апки (наприклад wishlist) або --list для списку")
    return run_app_debug(app_id, data_dir=args.data_dir)


if __name__ == "__main__":
    sys.exit(main())
