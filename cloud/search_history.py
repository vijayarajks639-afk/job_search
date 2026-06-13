"""
Per-user search history for the public cloud demo.

Privacy design
--------------
- Users are identified by the first 16 hex chars of SHA-256(email) — the raw
  email is NEVER stored.  The hash is derived at runtime from the resume the
  visitor uploads; no login is required.
- get_history() returns only the calling user's searches (matched by their hash).
- get_all_users() returns every user's name + searches — intended for the
  password-gated Admin tab only; never exposed to regular visitors.
- History is capped at 50 records per user; entries older than 7 days are pruned
  on every write.
- Stored in data/search_history.json — ephemeral on Streamlit Community Cloud
  (resets on app reboot; acceptable for a demo).
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config

_HISTORY_FILE = config.DATA_DIR / "search_history.json"
_LOCK = threading.Lock()
_MAX_PER_USER = 50
_KEEP_DAYS = 7          # prune entries older than this on every write
_DISPLAY_DAYS = 3       # default window for get_history / get_all_users


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load() -> dict:
    try:
        raw = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
        # Validate shape; reset silently if file is malformed or was created
        # by an older version with a different structure.
        if isinstance(raw, dict) and isinstance(raw.get("users"), dict):
            return raw
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"users": {}}


def _save(data: dict) -> None:
    _HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Public API ────────────────────────────────────────────────────────────────

def user_hash(email: str) -> str:
    """First 16 hex chars of SHA-256(lowercase email) — used as the storage key."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]


def record_search(uhash: str, display_name: str, domain: str,
                  companies: list[str], keywords: str, result_count: int) -> None:
    """Append a search record for this user. Thread-safe. Never raises — caller
    wraps in try/except so a history write never blocks a real search."""
    cutoff = _now() - timedelta(days=_KEEP_DAYS)
    with _LOCK:
        data = _load()
        users = data.setdefault("users", {})
        entry = users.setdefault(uhash, {
            "display_name": display_name or "User",
            "searches": [],
        })
        if display_name:
            entry["display_name"] = display_name
        entry["searches"].append({
            "ts": _now().isoformat(),
            "domain": domain,
            "companies": companies,
            "keywords": keywords,
            "results": result_count,
        })
        # Prune old entries, then cap total count.
        entry["searches"] = [
            s for s in entry["searches"]
            if datetime.fromisoformat(s["ts"]) >= cutoff
        ][-_MAX_PER_USER:]
        _save(data)


def get_history(uhash: str, days: int = _DISPLAY_DAYS) -> list[dict]:
    """Return this user's searches from the last `days` days, newest first.
    Returns empty list if no history or file not found."""
    cutoff = _now() - timedelta(days=days)
    data = _load()
    searches = data.get("users", {}).get(uhash, {}).get("searches", [])
    return [
        s for s in reversed(searches)
        if datetime.fromisoformat(s["ts"]) >= cutoff
    ]


def get_all_users(days: int = _DISPLAY_DAYS) -> list[dict]:
    """Return all users active in the last `days` days, newest-active first.
    Each entry: {"name": str, "searches": [newest-first list]}.
    Admin-only — never call from user-facing code."""
    cutoff = _now() - timedelta(days=days)
    data = _load()
    result = []
    for _uhash, udata in data.get("users", {}).items():
        recent = [
            s for s in udata.get("searches", [])
            if datetime.fromisoformat(s["ts"]) >= cutoff
        ]
        if recent:
            result.append({
                "name": udata.get("display_name", "Unknown"),
                "searches": list(reversed(recent)),   # newest first
            })
    # Sort by most-recent search across all users.
    return sorted(result, key=lambda u: u["searches"][0]["ts"], reverse=True)
