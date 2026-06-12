"""
Seed-source fetcher: routes each selected company to its verified ATS connector
(Workday / Darwinbox / Eightfold / Oracle ORC / SmartRecruiters / Greenhouse),
and falls back to the Adzuna aggregator for companies without a connector.

The broad agentic web-search sweep (agent_run.py) is the last resort — only
companies that neither a connector nor the aggregator covers reach it.

Usage:
    python fetch_jobs.py            # fetch, filter, write data/jobs_raw/<ts>.json
    python fetch_jobs.py --dry-run  # print per-source counts only, write nothing
    python fetch_jobs.py --companies "HSBC,Adobe"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

# UTF-8 console (Windows cp1252 chokes on some location names)
sys.stdout.reconfigure(encoding="utf-8")

import config
from sources import (workday, darwinbox, eightfold, oracle_orc,
                     smartrecruiters, greenhouse, adzuna)
from sources.companies import CONNECTED_COMPANIES, connector_for
from sources.base import JobPosting, is_recent, matches_location, dedupe


def _fetch_entry(entry: dict) -> list[JobPosting]:
    """Dispatch one registry entry to its platform connector."""
    platform = entry["platform"]
    name = entry["company"]
    if platform == "workday":
        return workday.fetch(company=name, host=entry["host"],
                             tenant=entry["tenant"], site=entry["site"],
                             applied_facets=entry.get("applied_facets"),
                             max_pages=15)
    if platform == "darwinbox":
        return darwinbox.fetch(company=name, host=entry["host"],
                               company_id=entry.get("company_id", "main"))
    if platform == "eightfold":
        return eightfold.fetch(company=name, host=entry["host"],
                               domain=entry["domain"])
    if platform == "oracle_orc":
        return oracle_orc.fetch(company=name, host=entry["host"],
                                site_number=entry["site_number"])
    if platform == "smartrecruiters":
        return smartrecruiters.fetch(company=name,
                                     company_id=entry["company_id"])
    if platform == "greenhouse":
        return greenhouse.fetch(company=name, board_token=entry["board_token"])
    raise ValueError(f"unknown platform: {platform}")


def _matches_selection(name: str, selected_lower: set[str]) -> bool:
    n = name.lower()
    return any(sel in n or n in sel for sel in selected_lower)


def fetch_all(companies_filter: str = "") -> tuple[list[JobPosting], dict]:
    """
    Fetch from every registered connector matching the selection.

    companies_filter — comma-separated string from the dashboard. When
    non-empty, only registry entries matching a selected company run.
    Empty string = full scheduled run, all connectors run.
    """
    selected_lower: set[str] = (
        {c.strip().lower() for c in companies_filter.split(",") if c.strip()}
        if companies_filter else set()
    )

    collected: list[JobPosting] = []
    status: dict[str, str] = {}
    for entry in CONNECTED_COMPANIES:
        name = entry["company"]
        if selected_lower and not _matches_selection(name, selected_lower):
            continue
        try:
            jobs = _fetch_entry(entry)
            collected.extend(jobs)
            status[name] = f"ok ({len(jobs)} fetched, {entry['platform']})"
        except Exception as e:  # network/HTTP/parse — record, don't crash the run
            status[name] = f"FAILED: {type(e).__name__}: {e}"
    return collected, status


def fetch_aggregator(companies: list[str]) -> tuple[list[JobPosting], dict]:
    """
    Adzuna fallback for companies with no direct connector. Silently skipped
    when ADZUNA_APP_ID / ADZUNA_APP_KEY are not configured.
    """
    if not config.AGGREGATOR_ENABLED or not companies:
        return [], {}
    collected: list[JobPosting] = []
    status: dict[str, str] = {}
    for name in companies:
        try:
            jobs = adzuna.fetch(company=name)
            collected.extend(jobs)
            status[name] = f"ok ({len(jobs)} fetched, adzuna)"
        except Exception as e:
            status[name] = f"FAILED: {type(e).__name__}: {e}"
    return collected, status


def apply_filters(postings: list[JobPosting]) -> list[JobPosting]:
    """
    Recency (unknown dates kept) + location only, then dedupe.
    Role *fitment* is deliberately left to the agentic step (which reads the full
    resume and JD context) — crude keyword gating here would drop good seed roles
    whose list view carries only a thin description.
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
    ap.add_argument("--companies", default="",
                    help="comma-separated companies (default: all registered)")
    args = ap.parse_args()

    config.ensure_dirs()
    raw, status = fetch_all(args.companies)
    filtered = apply_filters(raw)

    print("Seed sources:")
    for name, st in status.items():
        print(f"  - {name}: {st}")
    print(f"Fetched {len(raw)} raw -> {len(filtered)} after recency/location filters.")

    if args.dry_run:
        for p in filtered[:15]:
            print(f"    [{p.posted_date or p.posted_raw or 'date?'}] "
                  f"{p.company} — {p.title} — {p.location}")
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
