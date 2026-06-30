"""Перший час подій релогіну по акаунтах.

У режимі quiet_wallclock бот не пише WARNING «Сторінка вішліста без ознак кабінету…»
у БД — у експорті лишаються зазвичай лише ERROR/INFO про результат релогіну.

  python scripts/report_session_drop_times.py [runtime_logs.json]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RELOGIN_OK = "Повторний логін успішний"
RELOGIN_FAIL = "Повторний логін не вдався"


def first_ts(evs: list[dict], substr: str) -> str | None:
    hits = sorted(
        (r.get("created_at") or "")
        for r in evs
        if substr in (r.get("message") or "")
    )
    return hits[0] if hits else None


def main() -> int:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "export_today" / "runtime_logs.json"
    rows = json.loads(log_path.read_text(encoding="utf-8"))
    by_em: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        em = (r.get("email") or "").strip()
        if em:
            by_em[em].append(r)

    print(f"File: {log_path}")
    print()
    rows_out = []
    for em in sorted(by_em.keys(), key=str.casefold):
        evs = by_em[em]
        t_fail = first_ts(evs, RELOGIN_FAIL)
        t_ok = first_ts(evs, RELOGIN_OK)
        rows_out.append((em, t_fail, t_ok))

    print("email | перший fail релогіну (created_at UTC) | перший успіх релогіну")
    print("-" * 100)
    for em, tf, to in rows_out:
        print(f"{em} | {tf or '—'} | {to or '—'}")

    with_fail = [(em, tf) for em, tf, to in rows_out if tf]
    with_ok = [(em, to) for em, tf, to in rows_out if to]
    neither = [em for em, tf, to in rows_out if not tf and not to]
    print()
    print(f"З першим fail релогіну: {len(with_fail)}")
    if with_fail:
        times = sorted(t for _, t in with_fail)
        print(f"  діапазон першого fail: {times[0]} … {times[-1]}")
    print(f"З першим успішним релогіном: {len(with_ok)}")
    if with_ok:
        times = sorted(t for _, t in with_ok)
        print(f"  діапазон першого success: {times[0]} … {times[-1]}")
    print(f"Без жодного релогіну в логах: {len(neither)} {neither or ''}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
