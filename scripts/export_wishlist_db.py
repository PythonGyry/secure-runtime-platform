"""
Вигрузка з зашифрованої БД wishlist (логи та/або записи HTTP) у JSON.

Типовий dev-шлях (як у run_app_debug.py):
  runtime_logic/apps/wishlist/.dev_data/wishlist_secure.db

Приклади (з кореня репозиторію):
  python scripts/export_wishlist_db.py
  python scripts/export_wishlist_db.py --today
  python scripts/export_wishlist_db.py --today --out ./export_2026-05-04
  python scripts/export_wishlist_db.py --db "C:/path/to/wishlist_secure.db" --mode responses

Для збірки не в debug ключі мають збігатися з тими, що в runtime (інакше розшифрування не вдасться):
  --license-key / --hwid / --server-salt
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from runtime_logic.apps.wishlist.src.app.services.storage_service import EncryptedStorageService  # noqa: E402


def _default_db_path() -> Path:
    return PROJECT / "runtime_logic" / "apps" / "wishlist" / ".dev_data" / "wishlist_secure.db"


def _parse_db_timestamp(s: str) -> datetime | None:
    """Час у БД зазвичай з datetime.utcnow().isoformat() — трактуємо naive як UTC."""
    s = (s or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1]
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _local_day_bounds() -> tuple[datetime, datetime]:
    now = datetime.now().astimezone()
    start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    end = start + timedelta(days=1)
    return start, end


def _filter_by_today_responses(items: list[dict]) -> list[dict]:
    start, end = _local_day_bounds()
    out: list[dict] = []
    for it in items:
        ts = _parse_db_timestamp(str(it.get("timestamp") or ""))
        if ts is not None and start <= ts < end:
            out.append(it)
    return out


def _filter_by_today_logs(items: list[dict]) -> list[dict]:
    start, end = _local_day_bounds()
    out: list[dict] = []
    for it in items:
        ts = _parse_db_timestamp(str(it.get("created_at") or ""))
        if ts is not None and start <= ts < end:
            out.append(it)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Експорт logs / server_responses з wishlist_secure.db у JSON")
    parser.add_argument("--db", type=Path, default=_default_db_path(), help="Шлях до wishlist_secure.db")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Каталог для файлів (default: <repo>/export_wishlist_<timestamp>)",
    )
    parser.add_argument(
        "--mode",
        choices=("both", "responses", "logs"),
        default="both",
        help="Що вигрузити",
    )
    parser.add_argument(
        "--today",
        action="store_true",
        help="Лише записи за календарний «сьогодні» (локальний часовой пояс)",
    )
    parser.add_argument("--license-key", default="dev-debug-key", help="Ключ шифрування БД (dev за замовч.)")
    parser.add_argument("--hwid", default="dev-machine", help="HWID для ключа (dev за замовч.)")
    parser.add_argument("--server-salt", default="dev-salt", help="Сіль сервера (dev за замовч.)")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"Файл БД не знайдено: {args.db}", file=sys.stderr)
        return 1

    out_dir = args.out
    if out_dir is None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_dir = PROJECT / f"export_wishlist_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    storage = EncryptedStorageService(
        args.db,
        license_key=args.license_key,
        hwid=args.hwid,
        server_salt=args.server_salt,
    )

    if args.mode in ("both", "responses"):
        rows = storage.list_server_responses()
        if args.today:
            rows = _filter_by_today_responses(rows)
        path = out_dir / "server_responses.json"
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"server_responses: {len(rows)} записів -> {path}")

    if args.mode in ("both", "logs"):
        rows = storage.list_logs()
        if args.today:
            rows = _filter_by_today_logs(rows)
        path = out_dir / "runtime_logs.json"
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"logs: {len(rows)} записів -> {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
