"""Скільки акаунтів відновили сесію після розлогіну vs застрягли на Bank ID.

  python scripts/report_relogin_recovery.py [runtime_logs.json] [server_responses.json]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "export_today" / "runtime_logs.json"
    srv_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "export_today" / "server_responses.json"

    rows = json.loads(log_path.read_text(encoding="utf-8"))
    by_em: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        em = (r.get("email") or "").strip()
        if em:
            by_em[em].append(r)

    ok_msg = "Повторний логін успішний"
    fail_msg = "Повторний логін не вдався"
    exhaust_msg = "Вичерпано спроби повторного логіну"
    initial_fail = "Помилка початкового логіну"

    stats: list[dict] = []
    for em in sorted(by_em.keys(), key=str.casefold):
        evs = sorted(by_em[em], key=lambda x: x.get("created_at") or "")
        n_ok = sum(1 for r in evs if ok_msg in (r.get("message") or ""))
        n_fail = sum(1 for r in evs if fail_msg in (r.get("message") or ""))
        n_ex = sum(1 for r in evs if exhaust_msg in (r.get("message") or ""))
        n_init_fail = sum(1 for r in evs if initial_fail in (r.get("message") or ""))
        has_buy = any("Куплено товар" in (r.get("message") or "") for r in evs)
        has_prep = any("Дані для покупки готові" in (r.get("message") or "") for r in evs)

        recovered_at_least_once = n_ok > 0
        fail_after_ok = False
        if n_ok > 0 and n_fail > 0:
            t_ok = [r.get("created_at") for r in evs if ok_msg in (r.get("message") or "")]
            t_fail = [r.get("created_at") for r in evs if fail_msg in (r.get("message") or "")]
            first_ok_ts = min(t_ok) if t_ok else None
            if first_ok_ts:
                fail_after_ok = any((ft or "") > first_ok_ts for ft in t_fail)

        stats.append(
            {
                "email": em,
                "n_relogin_ok": n_ok,
                "n_relogin_fail": n_fail,
                "n_relogin_exhausted": n_ex,
                "n_initial_fail": n_init_fail,
                "recovered_at_least_once": recovered_at_least_once,
                "fail_after_recovery": fail_after_ok,
                "has_buy": has_buy,
                "has_prep": has_prep,
            }
        )

    s = stats
    with_recovery = [x for x in s if x["recovered_at_least_once"]]
    never_recovered = [x for x in s if x["n_relogin_fail"] > 0 and not x["recovered_at_least_once"]]
    recovered_clean = [x for x in s if x["recovered_at_least_once"] and x["n_relogin_fail"] == 0 and x["n_relogin_exhausted"] == 0]
    recovered_then_stuck = [
        x
        for x in s
        if x["recovered_at_least_once"] and (x["n_relogin_fail"] > 0 or x["n_relogin_exhausted"] > 0)
    ]

    print(f"File: {log_path}")
    print(f"Accounts: {len(s)}")
    print()
    print("=== З runtime_logs (текстові події) ===")
    print(f"Хоч 1 раз 'Повторний логін успішний' (сесію відновили після розлогіну): {len(with_recovery)}")
    print(f"  ... і потім БЕЗ 'не вдався' та БЕЗ 'вичерпано спроб': {len(recovered_clean)}")
    print(f"  ... але БУВ 'не вдався' або 'вичерпано' (застрягли на Bank ID після відновлення): {len(recovered_then_stuck)}")
    print(f"     з них fail ПІСЛЯ першого успішного релогіну: {sum(1 for x in recovered_then_stuck if x['fail_after_recovery'])}")
    print()
    print(f"'Повторний логін не вдався' хоч раз і ЖОДНОГО успішного релогіну: {len(never_recovered)}")
    print(f"'Помилка початкового логіну': {sum(1 for x in s if x['n_initial_fail'] > 0)}")
    print()

    if srv_path.is_file():
        data = json.loads(srv_path.read_text(encoding="utf-8"))
        bankid_by_em: dict[str, int] = defaultdict(int)
        cid_by_em: dict[str, int] = defaultdict(int)
        for r in data:
            if r.get("request_type") != "login_post":
                continue
            em = (r.get("email") or "").strip()
            u = str((r.get("request") or {}).get("url") or "").lower()
            if "login-bankid" in u:
                bankid_by_em[em] += 1
            elif "cid=" in u:
                cid_by_em[em] += 1

        print(f"=== З server_responses (фінальний URL після login_post) ===")
        print(f"Акаунтів з хоч одним login_post -> login-bankid.php: {sum(1 for em in bankid_by_em if bankid_by_em[em])}")
        print(f"Акаунтів з хоч одним login_post -> ?cid=... (без bankid у URL): {sum(1 for em in cid_by_em if cid_by_em[em])}")
        print()
        print("Кількість login_post на акаунт:")
        for label, d in ("bankid URL", bankid_by_em), ("cid URL", cid_by_em):
            vals = list(d.values())
            if vals:
                print(f"  {label}: min={min(vals)} max={max(vals)} sum={sum(vals)}")

    print()
    print("--- Детально: хто відновився, а потім упав ---")
    for x in recovered_then_stuck:
        print(
            f"  {x['email']}: ok={x['n_relogin_ok']} fail={x['n_relogin_fail']} ex={x['n_relogin_exhausted']} "
            f"buy={x['has_buy']} fail_after_ok={x['fail_after_recovery']}"
        )

    print()
    print("--- Ніколи не було успішного релогіну при наявності fail ---")
    for x in never_recovered:
        print(f"  {x['email']}: fail={x['n_relogin_fail']} prep={x['has_prep']} buy={x['has_buy']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
