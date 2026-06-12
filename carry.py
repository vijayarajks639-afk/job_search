"""
Carry-forward store for matched roles.

Web-search recall varies run-to-run, so a strong role found today may be missed by
tomorrow's searches. To keep the report stable and cumulative, we persist matches in
data/seen_matches.json and keep showing each for CARRY_FORWARD_DAYS days from when it
was first seen. The user verifies role status on the company site before applying.
"""

from __future__ import annotations

import json
from datetime import date

import config

STORE = config.DATA_DIR / "seen_matches.json"
CARRY_FORWARD_DAYS = 7


def _key(m: dict) -> str:
    url = (m.get("url") or "").strip().lower()
    if url:
        return url
    return f"{(m.get('company') or '').lower()}|{(m.get('title') or '').lower()}"


def _load() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {}


def merge(fresh_payload: dict) -> dict:
    """
    Merge this run's matches into the rolling store, expire stale entries, and
    return a payload whose `matches` is the union (deduped, sorted by fit).
    """
    store = _load()
    today = date.today().isoformat()
    fresh = fresh_payload.get("matches", []) or []
    fresh_keys = set()

    for m in fresh:
        k = _key(m)
        fresh_keys.add(k)
        if k in store:
            first_seen = store[k].get("first_seen", today)
            entry = dict(m)
            entry["first_seen"] = first_seen
            entry["last_seen"] = today
            store[k] = entry
        else:
            entry = dict(m)
            entry["first_seen"] = today
            entry["last_seen"] = today
            store[k] = entry

    # Expire entries older than the window (by first_seen).
    kept = {}
    for k, v in store.items():
        try:
            age = (date.today() - date.fromisoformat(v.get("first_seen", today))).days
        except ValueError:
            age = 0
        if age < CARRY_FORWARD_DAYS:
            kept[k] = v
    store = kept

    STORE.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")

    merged = dict(fresh_payload)
    merged["matches"] = sorted(store.values(),
                               key=lambda x: x.get("fit_score") or 0, reverse=True)
    merged["_carry"] = {
        "tracked": len(store),
        "new_this_run": len(fresh_keys),
        "carried_from_prior": max(0, len(store) - len(fresh_keys)),
    }
    return merged


def backfill_from_matched_files() -> int:
    """One-time: seed the store from existing matched_*.json files (recovers
    real matches found before carry-forward existed)."""
    import glob
    store = _load()
    today = date.today().isoformat()
    n = 0
    for f in sorted(glob.glob(str(config.JOBS_MATCHED_DIR / "matched_*.json"))):
        data = json.loads(open(f, encoding="utf-8").read())
        for m in data.get("matches", []):
            k = _key(m)
            if k not in store:
                entry = dict(m)
                entry["first_seen"] = today
                entry["last_seen"] = today
                store[k] = entry
                n += 1
    STORE.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
    return n
