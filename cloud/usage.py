"""
Usage tracking + Adzuna quota guard for the public cloud demo.

Two small JSON files under config.DATA_DIR:

  usage.json        — append-only event log: {"events": [{ts, kind, ...}, ...]}
                      kinds: "visit", "search", "error"
  adzuna_quota.json — daily API-call counter: {"date": "YYYY-MM-DD", "count": N}

Storage on Streamlit Community Cloud is ephemeral (lost on app reboot). That is
acceptable for v1: the quota counter only needs to survive a day, and usage
stats are indicative, not billing-grade. Upgrade path: Google Sheets / Supabase.

Writes are naive read-modify-write; concurrent sessions may rarely drop an
event. Fine for a demo — the quota cap errs on the safe side of Adzuna's
250 free calls/day anyway.
"""

from __future__ import annotations

import json
from datetime import datetime, date

import config

USAGE_FILE = config.DATA_DIR / "usage.json"
QUOTA_FILE = config.DATA_DIR / "adzuna_quota.json"
AI_QUOTA_FILE = config.DATA_DIR / "ai_quota.json"

# Public-demo guard rails for the free Adzuna tier (250 calls/day).
DAILY_CALL_CAP = 150          # global, across all visitors
MAX_COMPANIES_PER_SEARCH = 5  # 1 Adzuna call per company
MAX_SEARCHES_PER_SESSION = 3  # soft cap (resets on browser refresh)
MAX_EVENTS = 5000             # usage.json size guard

# AI fit-scoring guard rails (Anthropic Haiku, ~$0.007/analysis).
# Caps chosen to keep spend at ~$1–2/month even if fully used every day.
AI_DAILY_CAP = 8              # global analyses/day across all visitors
AI_MONTHLY_CAP = 200         # global analyses/month — hard stop
AI_PER_SESSION = 2           # soft cap per browser session


def _load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path, obj) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    except Exception:
        pass  # never let bookkeeping break the app


# ── Event log ────────────────────────────────────────────────────────────────

def log_event(kind: str, **fields) -> None:
    """Append one event ({ts, kind, **fields}) to usage.json."""
    data = _load(USAGE_FILE, {"events": []})
    events = data.get("events", [])
    events.append({"ts": datetime.now().isoformat(timespec="seconds"),
                   "kind": kind, **fields})
    if len(events) > MAX_EVENTS:
        events = events[-MAX_EVENTS:]
    _save(USAGE_FILE, {"events": events})


def summary() -> dict:
    """Aggregate stats for the admin page / usage email."""
    events = _load(USAGE_FILE, {"events": []}).get("events", [])
    today = date.today().isoformat()

    visits = [e for e in events if e["kind"] == "visit"]
    searches = [e for e in events if e["kind"] == "search"]
    errors = [e for e in events if e["kind"] == "error"]

    by_domain: dict[str, int] = {}
    by_company: dict[str, int] = {}
    for s in searches:
        d = s.get("domain", "?")
        by_domain[d] = by_domain.get(d, 0) + 1
        for c in s.get("companies", []):
            by_company[c] = by_company.get(c, 0) + 1

    scores = [e for e in events if e["kind"] == "ai_score"]
    aiq = _ai_quota()
    return {
        "since": events[0]["ts"] if events else None,
        "visits_total": len(visits),
        "visits_today": sum(1 for e in visits if e["ts"].startswith(today)),
        "searches_total": len(searches),
        "searches_today": sum(1 for e in searches if e["ts"].startswith(today)),
        "errors_total": len(errors),
        "top_domains": sorted(by_domain.items(), key=lambda x: -x[1])[:5],
        "top_companies": sorted(by_company.items(), key=lambda x: -x[1])[:10],
        "last_errors": errors[-3:],
        "quota_used_today": quota_used(),
        "quota_cap": DAILY_CALL_CAP,
        "ai_total": len(scores),
        "ai_used_today": aiq["day_count"],
        "ai_daily_cap": AI_DAILY_CAP,
        "ai_used_month": aiq["month_count"],
        "ai_monthly_cap": AI_MONTHLY_CAP,
    }


# ── Adzuna daily quota ───────────────────────────────────────────────────────

def _quota() -> dict:
    q = _load(QUOTA_FILE, {})
    today = date.today().isoformat()
    if q.get("date") != today:
        q = {"date": today, "count": 0}
    return q


def quota_used() -> int:
    return _quota()["count"]


def quota_remaining() -> int:
    return max(0, DAILY_CALL_CAP - quota_used())


def consume_quota(n_calls: int) -> bool:
    """Reserve n API calls. Returns False (and consumes nothing) if over cap."""
    q = _quota()
    if q["count"] + n_calls > DAILY_CALL_CAP:
        return False
    q["count"] += n_calls
    _save(QUOTA_FILE, q)
    return True


# ── Anthropic AI-scoring quota (daily + monthly) ─────────────────────────────

def _ai_quota() -> dict:
    q = _load(AI_QUOTA_FILE, {})
    today = date.today().isoformat()
    month = today[:7]  # "YYYY-MM"
    if q.get("date") != today:
        q["date"] = today
        q["day_count"] = 0
    if q.get("month") != month:
        q["month"] = month
        q["month_count"] = 0
    q.setdefault("day_count", 0)
    q.setdefault("month_count", 0)
    return q


def ai_quota_used() -> int:
    return _ai_quota()["day_count"]


def ai_quota_remaining() -> int:
    q = _ai_quota()
    return max(0, min(AI_DAILY_CAP - q["day_count"],
                      AI_MONTHLY_CAP - q["month_count"]))


def consume_ai_quota(n: int = 1) -> bool:
    """Reserve n AI analyses. False (consumes nothing) if over daily OR monthly cap."""
    q = _ai_quota()
    if q["day_count"] + n > AI_DAILY_CAP or q["month_count"] + n > AI_MONTHLY_CAP:
        return False
    q["day_count"] += n
    q["month_count"] += n
    _save(AI_QUOTA_FILE, q)
    return True
