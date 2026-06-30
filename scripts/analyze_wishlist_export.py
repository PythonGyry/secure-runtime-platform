"""Aggregate purchase stats from export_today (runtime_logs + server_responses).

  python scripts/analyze_wishlist_export.py [path/to/export_dir]

Defaults to <repo>/export_today.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "export_today"
    logs_path = out_dir / "runtime_logs.json"
    srv_path = out_dir / "server_responses.json"
    if not logs_path.is_file():
        print(f"Missing {logs_path}", file=sys.stderr)
        return 1

    logs = json.loads(logs_path.read_text(encoding="utf-8"))
    re_kup = re.compile(r"Куплено товар\s+(\d+)")
    re_fail_line = re.compile(r"Помилка при покупці товару\s+(\d+)")
    re_prep_ok = re.compile(r"Дані для покупки готові")
    re_pokupka_ok = re.compile(r"Покупка успішна на спробі")

    success_pairs: set[tuple[str, str]] = set()
    kup_lines = 0
    fail_lines = 0
    prep_ready_by_email: set[str] = set()
    purchase_success_attempt_lines = 0

    for row in logs:
        msg = row.get("message", "") or ""
        em = row.get("email", "") or ""
        if "Куплено товар" in msg:
            kup_lines += 1
        if "Помилка при покупці товару" in msg:
            fail_lines += 1
        if re_prep_ok.search(msg) and em:
            prep_ready_by_email.add(em)
        if re_pokupka_ok.search(msg):
            purchase_success_attempt_lines += 1
        for m in re_kup.finditer(msg):
            success_pairs.add((em, m.group(1)))

    print(f"=== {out_dir} (runtime_logs.json) ===")
    print(f"Accounts reached 'Дані для покупки готові' (unique email): {len(prep_ready_by_email)}")
    print(f"Lines 'Покупка успішна на спробі': {purchase_success_attempt_lines}")
    print(f"Lines 'Куплено товар …': {kup_lines}")
    print(f"Unique successful (email, product_id): {len(success_pairs)}")
    print(f"Lines 'Помилка при покупці товару': {fail_lines}")

    pid_counts: dict[str, int] = {}
    email_pids: dict[str, set[str]] = {}
    for em, pid in success_pairs:
        pid_counts[pid] = pid_counts.get(pid, 0) + 1
        email_pids.setdefault(em, set()).add(pid)
    n_skus = len(pid_counts)
    full_multi = sum(1 for _em, pids in email_pids.items() if len(pids) >= n_skus and n_skus > 0)
    print(f"Accounts with at least one 'Куплено товар' log: {len(email_pids)}")
    print(f"Accounts with all {n_skus} product ids bought (per log): {full_multi}")
    if pid_counts:
        print("Successful purchases per product_id (how many accounts):")
        for pid in sorted(pid_counts, key=lambda x: int(x)):
            print(f"  id={pid}: {pid_counts[pid]}")

    planned_slots = len(prep_ready_by_email) * n_skus if n_skus else 0
    print()
    print(f"Heuristic 'planned' completions (prep-ready accounts * SKUs): {planned_slots}")
    print(f"Actual unique successful (email, product_id): {len(success_pairs)}")

    if not srv_path.is_file():
        return 0

    srv = json.loads(srv_path.read_text(encoding="utf-8"))
    purch = [r for r in srv if r.get("request_type") == "purchase"]
    print()
    print(f"=== {out_dir} (server_responses.json) ===")
    print(f"HTTP records request_type=purchase: {len(purch)}")
    sc200 = sum(1 for r in purch if (r.get("response") or {}).get("status_code") == 200)
    print(f"  ... status_code==200: {sc200}")
    js_true = 0
    js_false = 0
    for r in purch:
        j = (r.get("response") or {}).get("json")
        if isinstance(j, dict):
            if j.get("success") is True:
                js_true += 1
            elif j.get("success") is False:
                js_false += 1
    print(f"  ... response.json.success==true: {js_true}")
    print(f"  ... response.json.success==false: {js_false}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
