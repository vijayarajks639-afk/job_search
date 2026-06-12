"""
Shared types and helpers for job source connectors.

Every connector returns a list of `JobPosting`. The orchestrator (`fetch_jobs.py`)
handles recency filtering, location/role filtering, and de-duplication using the
helpers here so individual connectors stay thin.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass
class JobPosting:
    company: str
    title: str
    location: str
    url: str
    source: str                       # connector name, e.g. "workday"
    posted_date: Optional[str] = None  # ISO date "YYYY-MM-DD" if known
    posted_raw: str = ""               # original relative text e.g. "Posted 3 Days Ago"
    description: str = ""              # JD text/snippet when available
    job_id: str = ""

    def fingerprint(self) -> str:
        """Stable id for de-duplication across sources."""
        key = f"{self.company.lower()}|{self.title.lower().strip()}|{self.location.lower().strip()}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fingerprint"] = self.fingerprint()
        return d


# ── Relative-date parsing (Workday/Eightfold list views) ─────────────────────
_REL_PATTERNS = [
    (re.compile(r"posted\s+today", re.I), 0),
    (re.compile(r"posted\s+yesterday", re.I), 1),
    (re.compile(r"(\d+)\s*\+?\s*days?\s+ago", re.I), None),   # capture group => N
    (re.compile(r"(\d+)\s*\+?\s*hours?\s+ago", re.I), 0),
]


def parse_relative_posted(text: str) -> Optional[str]:
    """
    Convert a relative 'posted' string to an ISO date.
    Returns None if it cannot be parsed (caller decides how to treat unknowns).
    '30+ Days Ago' parses as 30 days (i.e. clearly older than a week).
    """
    if not text:
        return None
    t = text.strip()
    for pat, fixed_days in _REL_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        days = fixed_days if fixed_days is not None else int(m.group(1))
        return (date.today() - timedelta(days=days)).isoformat()
    # Try an explicit date like 2026-06-10 or 10/06/2026
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def is_recent(posting: JobPosting, days: int) -> Optional[bool]:
    """
    True/False if recency is known, None if the posting date is unknown.
    Unknown dates are kept by default (better to over-include than silently drop),
    but flagged so the report can show 'date unknown'.
    """
    if not posting.posted_date:
        return None
    try:
        pd = date.fromisoformat(posting.posted_date)
    except ValueError:
        return None
    return (date.today() - pd).days <= days


def matches_location(posting: JobPosting, targets: list[str]) -> bool:
    loc = posting.location.lower()
    return any(t in loc for t in targets) if targets else True


def matches_role(posting: JobPosting, keywords: list[str]) -> bool:
    hay = f"{posting.title} {posting.description}".lower()
    return any(k in hay for k in keywords) if keywords else True


def dedupe(postings: list[JobPosting]) -> list[JobPosting]:
    seen: set[str] = set()
    out: list[JobPosting] = []
    for p in postings:
        fp = p.fingerprint()
        if fp in seen:
            continue
        seen.add(fp)
        out.append(p)
    return out
