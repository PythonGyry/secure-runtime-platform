"""
Вигрузка пакетів на Linux-сервер (збірка на Windows → SFTP на сервер).

Запуск з кореня проекту:
  python scripts/deploy_to_server.py --host my.server.com --user root --path /path/to/secure-runtime-platform
  python scripts/deploy_to_server.py --build --build-client --server-url https://my.server.com --host ... --user ... --path ...

Опціонально: deploy_config.json у корені (не комітити) або змінні середовища:
  DEPLOY_HOST, DEPLOY_USER, DEPLOY_PATH, DEPLOY_KEY, DEPLOY_PASSWORD, DEPLOY_SERVER_URL

Потрібно: pip install paramiko
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    cfg = {}
    env_map = {
        "DEPLOY_HOST": "host",
        "DEPLOY_USER": "user",
        "DEPLOY_PATH": "path",
        "DEPLOY_KEY": "key_path",
        "DEPLOY_PASSWORD": "password",
        "DEPLOY_SERVER_URL": "server_url",
    }
    for env, key in env_map.items():
        if env in os.environ and os.environ[env].strip():
            cfg[key] = os.environ[env].strip()
    config_file = PROJECT / "deploy_config.json"
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            for k, v in data.items():
                if v is not None and str(v).strip():
                    cfg[k] = str(v).strip()
        except Exception as e:
            print(f"Warning: could not read {config_file}: {e}", file=sys.stderr)
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Зібрати (опціонально) та вигрузити backend/packages на Linux-сервер через SFTP",
    )
    parser.add_argument("--host", "-H", help="Хост сервера (напр. my.server.com або IP)")
    parser.add_argument("--user", "-u", help="SSH користувач")
    parser.add_argument("--path", "-p", help="Шлях до проекту на сервері (напр. /path/to/secure-runtime-platform)")
    parser.add_argument("--key", "-k", help="Шлях до SSH ключа (опціонально)")
    parser.add_argument("--password", dest="password", help="Пароль SSH (краще через DEPLOY_PASSWORD)")
    parser.add_argument("--build", "-b", action="store_true", help="Спочатку зібрати: manager.py build")
    parser.add_argument("--build-client", action="store_true", help="Зібрати .exe клієнт з --server-url")
    parser.add_argument("--server-url", "-s", help="URL сервера для клієнта (напр. https://your-server.com)")
    parser.add_argument("--app", "-a", default="wishlist", help="App для build/build-client (default: wishlist)")
    parser.add_argument("--version", "-v", default="1.0.0", help="Версія для build (default: 1.0.0)")
    parser.add_argument("--client-name", "-n", help="Ім'я exe клієнта (default: <app>_bootstrap)")
    parser.add_argument("--dry-run", action="store_true", help="Тільки показати, що буде зроблено")
    args = parser.parse_args()

    cfg = load_config()
    host = args.host or cfg.get("host")
    user = args.user or cfg.get("user")
    path = args.path or cfg.get("path")
    key_path = args.key or cfg.get("key_path")
    password = args.password or cfg.get("password")
    server_url = args.server_url or cfg.get("server_url")

    if not host or not user or not path:
        print("Потрібні --host, --user, --path (або deploy_config.json / змінні DEPLOY_*)", file=sys.stderr)
        return 1

    path = path.rstrip("/")

    if args.dry_run:
        print("Dry run. Would:")
        if args.build:
            print(f"  - manager.py build -a {args.app} -v {args.version}")
        if args.build_client:
            print(f"  - manager.py client -a {args.app} -n {args.client_name or args.app + '_bootstrap'} --server-url {server_url or '(not set)'}")
        print(f"  - SFTP upload backend/packages/ -> {user}@{host}:{path}/backend/packages/")
        return 0

    # 1) Збірка пакетів
    if args.build:
        print("Building runtime packages...")
        r = subprocess.run(
            [sys.executable, "manager.py", "build", "-a", args.app, "-v", args.version],
            cwd=PROJECT,
        )
        if r.returncode != 0:
            return r.returncode
        print("Build done.")

    # 2) Збірка клієнта з URL сервера (щоб .exe одразу йшов на ваш сервер)
    if args.build_client:
        if not server_url:
            print("Для --build-client потрібен --server-url (напр. https://your-server.com)", file=sys.stderr)
            return 1
        client_name = args.client_name or f"{args.app}_bootstrap"
        print(f"Building client exe ({client_name}) with server URL {server_url}...")
        cmd = [sys.executable, "manager.py", "client", "-a", args.app, "-n", client_name, "--server-url", server_url]
        r = subprocess.run(cmd, cwd=PROJECT)
        if r.returncode != 0:
            return r.returncode
        print("Client build done.")

    # 3) Вигрузка backend/packages на сервер
    packages_dir = PROJECT / "backend" / "packages"
    if not packages_dir.exists():
        print("Папка backend/packages/ не знайдена. Запустіть спочатку: python manager.py build -a <app> -v <ver>", file=sys.stderr)
        return 1

    files = list(packages_dir.iterdir())
    if not files:
        print("backend/packages/ порожня. Нічого вигружати.", file=sys.stderr)
        return 1

    try:
        import paramiko
    except ImportError:
        print("Потрібна бібліотека paramiko: pip install paramiko", file=sys.stderr)
        return 1

    print(f"Uploading to {user}@{host}:{path}/backend/packages/ ...")
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kw = {"hostname": host, "username": user, "port": 22}
        if key_path:
            connect_kw["key_filename"] = key_path
        if password:
            connect_kw["password"] = password
        client.connect(**connect_kw)
        sftp = client.open_sftp()

        remote_packages = f"{path}/backend/packages"
        try:
            sftp.stat(remote_packages)
        except FileNotFoundError:
            parts = remote_packages.strip("/").split("/")
            for i in range(1, len(parts) + 1):
                sub = "/" + "/".join(parts[:i])
                try:
                    sftp.stat(sub)
                except FileNotFoundError:
                    sftp.mkdir(sub)

        for f in files:
            if f.is_file():
                remote_path = f"{remote_packages}/{f.name}"
                sftp.put(str(f), remote_path)
                print(f"  uploaded {f.name}")

        sftp.close()
        client.close()
    except Exception as e:
        print(f"SFTP error: {e}", file=sys.stderr)
        return 1

    print("Done. Пакети на сервері. У адмінці на сервері переконайтесь, що Client Bootstrap URL вказано правильно.")
    if args.build_client and server_url:
        print(f"  .exe клієнт у dist/ — можна роздавати користувачам; він підключається до {server_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
