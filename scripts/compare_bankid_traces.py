"""
Порівняння HTTP-трас (server_responses) для акаунтів «купили» vs «з релогін/Bank ID».

  python scripts/compare_bankid_traces.py [runtime_logs.json] [server_responses.json]

Шукає останні записи перед (а) першим «Куплено товар» або (б) першим «Повторний логін не вдався»,
та порівнює маркери в обрізаному HTML wishlist.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRE_WINDOW = 8  # скільки HTTP-подій показати перед інцидентом


def _wishlist_markers(text: str | None) -> dict[str, bool]:
    if not text:
        return {}
    t = text
    low = t.lower()
    return {
        "has_span_name": "span-name" in low,
        "has_wishlist_table": "wishlist_table" in low,
        "has_login_php": "login.php" in low,
        "has_bankid": "bankid" in low or "bank id" in low,
        "title_auth": bool(re.search(r"<title>\s*авторизац", low)),
    }


def _tail_url(url: str) -> str:
    if not url:
        return ""
    u = url.replace("https://coins.bank.gov.ua/", "")
    return u[:88]


def main() -> int:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "export_today" / "runtime_logs.json"
    srv_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "export_today" / "server_responses.json"

    rows = json.loads(log_path.read_text(encoding="utf-8"))
    by_email_logs: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        em = (r.get("email") or "").strip()
        if em:
            by_email_logs[em].append(r)

    first_buy_ts: dict[str, str] = {}
    first_relogin_fail_ts: dict[str, str] = {}
    for em, evs in by_email_logs.items():
        evs = sorted(evs, key=lambda x: x.get("created_at") or "")
        for r in evs:
            msg = r.get("message", "") or ""
            ts = r.get("created_at") or ""
            if "Куплено товар" in msg and em not in first_buy_ts:
                first_buy_ts[em] = ts
            if "Повторний логін не вдався" in msg and em not in first_relogin_fail_ts:
                first_relogin_fail_ts[em] = ts

    bought_ok = set(first_buy_ts.keys())
    rel_fail = set(first_relogin_fail_ts.keys())
    bought_only = bought_ok - rel_fail
    fail_only = rel_fail - bought_ok
    both = bought_ok & rel_fail

    print("=== З логів (runtime_logs) ===")
    print(f"Унікальні email: {len(by_email_logs)}")
    print(f"Є 'Куплено товар': {len(bought_ok)}")
    print(f"Є 'Повторний логін не вдався': {len(rel_fail)}")
    print(f"Тільки купили (без релогін-ERR у логах): {len(bought_only)}")
    print(f"Тільки релогін-фейл (без рядка купівлі): {len(fail_only)}")
    print(f"І купівля, і був релогін-ERR: {len(both)}")
    if both:
        print("  emails:", ", ".join(sorted(both)))
    print()

    print("=== Час (UTC, поле created_at) — перший релогін-фейл vs перша купівля ===")
    fail_times = list(first_relogin_fail_ts.values())
    buy_times = list(first_buy_ts.values())
    if fail_times:
        print(f"мін..макс перший relogin_fail: {min(fail_times)} .. {max(fail_times)}")
    if buy_times:
        print(f"мін..макс перша купівля:     {min(buy_times)} .. {max(buy_times)}")
    print()

     

    data = json.loads(srv_path.read_text(encoding="utf-8"))
    by_srv: dict[str, list[dict]] = defaultdict(list)
    for r in data:
        em = (r.get("email") or "").strip()
        if em:
            by_srv[em].append(r)
    for em in by_srv:
        by_srv[em].sort(key=lambda x: x.get("timestamp") or "")

    def print_window(label: str, em: str, cutoff_ts: str) -> None:
        recs = by_srv.get(em, [])
        before = [r for r in recs if (r.get("timestamp") or "") <= cutoff_ts]
        win = before[-PRE_WINDOW:] if before else []
        print(f"--- {label} {em} cutoff={cutoff_ts} ---")
        for r in win:
            rq = r.get("request") or {}
            rs = r.get("response") or {}
            print(
                f"  {r.get('timestamp')} {r.get('request_type')} sc={rs.get('status_code')} "
                f"{_tail_url(str(rq.get('url') or ''))}"
            )
        if win:
            last = win[-1]
            tx = (last.get("response") or {}).get("text") or ""
            mk = _wishlist_markers(tx if last.get("request_type") == "get_page" else None)
            if last.get("request_type") == "get_page":
                print(f"     last get_page markers: {mk}")
        print()

    print(f"=== Останні {PRE_WINDOW} HTTP перед першим relogin_fail (приклади з fail_only) ===")
    for em in sorted(fail_only)[:5]:
        print_window("FAIL", em, first_relogin_fail_ts[em])

    print(f"=== Останні {PRE_WINDOW} HTTP перед першою купівлею (приклади з bought_only) ===")
    for em in sorted(bought_only)[:5]:
        print_window("OK", em, first_buy_ts[em])

    # Агрегат: останній wishlist get_page перед інцидентом
    def last_wishlist_before(em: str, cutoff_ts: str) -> dict | None:
        recs = by_srv.get(em, [])
        candidates = [
            r
            for r in recs
            if (r.get("timestamp") or "") <= cutoff_ts
            and r.get("request_type") == "get_page"
            and "wishlist.php" in str((r.get("request") or {}).get("url") or "")
        ]
        return candidates[-1] if candidates else None

    print("=== Останній login_post перед першим relogin_fail (фінальний URL після редіректу) ===")
    fail_post_urls = []
    for em, ts in first_relogin_fail_ts.items():
        recs = [r for r in by_srv.get(em, []) if (r.get("timestamp") or "") <= ts]
        for r in reversed(recs):
            if r.get("request_type") != "login_post":
                continue
            u = str((r.get("request") or {}).get("url") or "")
            fail_post_urls.append(u)
            break
    fc_u = Counter(fail_post_urls)
    for u, n in fc_u.most_common(10):
        print(f"  x{n} {u[:100]}")

    def in_655_657(ts: str) -> bool:
        if not ts:
            return False
        return ts.startswith("2026-05-04T06:55") or ts.startswith("2026-05-04T06:56") or ts.startswith("2026-05-04T06:57")

    print("=== login_post у вікні 06:55–06:57 UTC для акаунтів «тільки купили» (немає relogin ERR) ===")
    ok_sample = sorted(bought_only)[:12]
    for em in ok_sample:
        recs = by_srv.get(em, [])
        posts = [r for r in recs if r.get("request_type") == "login_post" and in_655_657(r.get("timestamp") or "")]
        if not posts:
            print(f"  {em}: (немає login_post у цьому вікні)")
            continue
        u = str((posts[-1].get("request") or {}).get("url") or "")
        print(f"  {em}: {u[:100]}")

    print()
    print("=== Що йде одразу перед relogin_fail: тип запису перед першим login_get після останнього wishlist ===")
    # For fail accounts: find sequence ... get_page wishlist, login_get, login_post — record types in 4 slots before fail log time
    chain4_fail = Counter()
    chain4_ok = Counter()
    for em, ts in first_relogin_fail_ts.items():
        recs = by_srv.get(em, [])
        before = [r for r in recs if (r.get("timestamp") or "") <= ts]
        tail = [r.get("request_type") for r in before[-4:]]
        chain4_fail[tuple(tail)] += 1
    for em, ts in first_buy_ts.items():
        recs = by_srv.get(em, [])
        before = [r for r in recs if (r.get("timestamp") or "") <= ts]
        tail = [r.get("request_type") for r in before[-4:]]
        chain4_ok[tuple(tail)] += 1
    print("TOP chains before relogin_fail (last 4 request_types):", chain4_fail.most_common(8))
    print("TOP chains before buy (last 4 request_types):", chain4_ok.most_common(8))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
