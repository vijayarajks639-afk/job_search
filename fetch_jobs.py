"""
Seed-source fetcher: pulls exact, dated postings from verified Workday endpoints
(currently CBA + The Standard) to prime the agentic search step.

This is intentionally small — the broad sweep across all GCCs happens in the
agentic web-search step (agent_run.py). Seeds give us free, reliable, dated data.

Usage:
    python fetch_jobs.py            # fetch, filter, write data/jobs_raw/<ts>.json
    python fetch_jobs.py --dry-run  # print per-source counts only, write nothing
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

# UTF-8 console (Windows cp1252 chokes on some location names)
sys.stdout.reconfigure(encoding="utf-8")

import config
from sources import workday, darwinbox
from sources.companies import WORKDAY_SEEDS, DARWINBOX_SEEDS
from sources.base import JobPosting, is_recent, matches_location, dedupe


def fetch_all() -> tuple[list[JobPosting], dict]:
    """Returns (postings, per_source_status)."""
    collected: list[JobPosting] = []
    status: dict[str, str] = {}
    for seed in WORKDAY_SEEDS:
        name = seed["company"]
        try:
            jobs = workday.fetch(
                company=name,
                host=seed["host"],
                tenant=seed["tenant"],
                site=seed["site"],
                applied_facets=seed.get("applied_facets"),
                max_pages=15,
            )
            collected.extend(jobs)
            status[name] = f"ok ({len(jobs)} fetched)"
        except Exception as e:  # network/HTTP/parse — record, don't crash the run
            status[name] = f"FAILED: {type(e).__name__}: {e}"

    for seed in DARWINBOX_SEEDS:
        name = seed["company"]
        try:
            jobs = darwinbox.fetch(
                company=name,
                host=seed["host"],
                company_id=seed.get("company_id", "main"),
            )
            collected.extend(jobs)
            status[name] = f"ok ({len(jobs)} fetched)"
        except Exception as e:
            status[name] = f"FAILED: {type(e).__name__}: {e}"
    return collected, status


def apply_filters(postings: list[JobPosting]) -> list[JobPosting]:
    """
    Recency (unknown dates kept) + location only, then dedupe.
    Role *fitment* is deliberately left to the agentic step (which reads the full
    resume and JD context) — crude keyword gating here would drop good seed roles
    whose Workday list view carries only a thin description.
    """
    out = []
    for p in postings:
        if is_recent(p, config.RECENT_DAYS) is False:   # known-old → drop
            continue
        if not matches_location(p, config.TARGET_LOCATIONS):
            continue
        out.append(p)
    return dedupe(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    config.ensure_dirs()
    raw, status = fetch_all()
    filtered = apply_filters(raw)

    print("Seed sources:")
    for name, st in status.items():
        print(f"  - {name}: {st}")
    print(f"Fetched {len(raw)} raw -> {len(filtered)} after recency/role/location filters.")

    if args.dry_run:
        for p in filtered[:15]:
            print(f"    [{p.posted_raw or 'date?'}] {p.title} — {p.location}")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = config.JOBS_RAW_DIR / f"seeds_{ts}.json"
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_status": status,
        "count": len(filtered),
        "postings": [p.to_dict() for p in filtered],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
