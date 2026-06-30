"""Analyze runtime_logs.json: initial vs prep vs monitoring failures per account."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "export_today" / "runtime_logs.json"
    rows = json.loads(log_path.read_text(encoding="utf-8"))

    by_email: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        em = (r.get("email") or "").strip()
        if not em:
            continue
        by_email[em].append(r)

    markers = {
        "monitor_start": "Моніторинг запущено",
        "prep_ready": "Дані для покупки готові",
        "relogin_fail": "Повторний логін не вдався",
        "relogin_exhausted": "Вичерпано спроби повторного логіну",
        "bought": "Куплено товар",
    }

    report: list[dict] = []
    for em in sorted(by_email.keys(), key=str.casefold):
        evs = sorted(by_email[em], key=lambda r: r.get("created_at") or "")
        idx = {k: None for k in markers}
        for r in evs:
            msg = r.get("message", "") or ""
            for k, sub in markers.items():
                if sub in msg and idx[k] is None:
                    idx[k] = r.get("created_at")
        fail_phase = None
        fail_ts = None
        for r in evs:
            if r.get("level") != "ERROR":
                continue
            msg = r.get("message", "") or ""
            ca = r.get("created_at")
            if "Помилка початкового логіну" in msg:
                fail_phase, fail_ts = "initial_login", ca
                break
            if "Повторний логін не вдався" in msg:
                prep_t = idx["prep_ready"]
                if prep_t and ca and ca >= prep_t:
                    fail_phase = "monitoring_reauth"
                else:
                    fail_phase = "reauth_before_prep_ready"
                fail_ts = ca
                break
            if "Вичерпано спроби повторного логіну" in msg:
                prep_t = idx["prep_ready"]
                if prep_t and ca and ca >= prep_t:
                    fail_phase = "monitoring_reauth_exhausted"
                else:
                    fail_phase = "prep_reauth_exhausted"
                fail_ts = ca
                break
        prep_t = idx["prep_ready"]
        rel_t = idx["relogin_fail"]
        rel_after_prep = bool(prep_t and rel_t and rel_t >= prep_t)
        rel_before_prep = bool(prep_t and rel_t and rel_t < prep_t)
        any_rel_after_prep = False
        if prep_t:
            for r in evs:
                if (r.get("message") or "").find("Повторний логін не вдався") < 0:
                    continue
                ca = r.get("created_at") or ""
                if ca >= prep_t:
                    any_rel_after_prep = True
                    break
        report.append(
            {
                "email": em,
                "first_log": evs[0].get("created_at"),
                "monitor_start": idx["monitor_start"],
                "prep_ready": idx["prep_ready"],
                "first_buy": idx["bought"],
                "first_relogin_fail": idx["relogin_fail"],
                "relogin_exhausted": idx["relogin_exhausted"],
                "first_error_phase": fail_phase,
                "first_error_ts": fail_ts,
                "relogin_fail_after_prep": rel_after_prep,
                "relogin_fail_before_prep": rel_before_prep,
                "any_relogin_fail_after_prep": any_rel_after_prep,
                "bought_any": idx["bought"] is not None,
                "prep_ok": idx["prep_ready"] is not None,
            }
        )

    print(f"=== File: {log_path}")
    print(f"Unique accounts (emails in logs): {len(report)}")
    fc = Counter(x["first_error_phase"] for x in report)
    print("First classified ERROR:", dict(fc))
    print(f"Reached prep (msg 'Дані для покупки готові'): {sum(1 for x in report if x['prep_ok'])}")
    print(f"At least one 'Куплено товар': {sum(1 for x in report if x['bought_any'])}")

    rel = [x for x in report if x["first_relogin_fail"]]
    after_prep = sum(1 for x in rel if x["relogin_fail_after_prep"])
    any_after = sum(1 for x in report if x["any_relogin_fail_after_prep"])
    print()
    print(f"Accounts with any 'Повторний логін не вдався': {len(rel)}")
    print(f"  First such log strictly AFTER prep_ready timestamp: {after_prep}")
    print(f"  At least one such log after prep (monitoring): {any_after}")
    print(f"  First such log BEFORE prep_ready (early LIST/reauth): {sum(1 for x in rel if x['relogin_fail_before_prep'])}")

    print()
    print("--- per account ---")
    for x in report:
        ap = "after_prep" if x["any_relogin_fail_after_prep"] else ""
        print(
            f"{x['email'][:36]:<36} prep={str(x['prep_ok']):5} buy={str(x['bought_any']):5} "
            f"1st_err={str(x['first_error_phase']):28} rel_after_prep={str(x['any_relogin_fail_after_prep']):5} {ap}"
        )

    mins = []
    for x in rel:
        t = x["first_relogin_fail"] or ""
        if len(t) >= 16:
            mins.append(t[11:16])
    print()
    print("UTC HH:MM of first relogin fail:", Counter(mins).most_common(15))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
