"""
Generic Greenhouse job board connector.

Public unauthenticated boards API:

    GET https://boards-api.greenhouse.io/v1/boards/<board_token>/jobs

Response: {"jobs": [{id, title, absolute_url, updated_at,
location: {name}, ...}], "meta": {"total": N}}.

Greenhouse does not expose a posted date in the list view — `updated_at` is the
closest signal and is used as posted_date (a refreshed posting looks new; that
is acceptable for a recency-biased pipeline). India filtering is client-side.
"""

from __future__ import annotations

import requests

import config
from sources.base import JobPosting

API = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

_INDIA_HINTS = ("india", "bengaluru", "bangalore", "hyderabad", "pune",
                "chennai", "mumbai", "gurgaon", "gurugram", "noida", "delhi", "remote")


def fetch(company: str, board_token: str,
          india_only: bool = True) -> list[JobPosting]:
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    resp = requests.get(API.format(board_token=board_token),
                        headers=headers, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])

    results: list[JobPosting] = []
    for j in jobs:
        loc = ((j.get("location") or {}).get("name") or "").strip()
        if india_only and not any(h in loc.lower() for h in _INDIA_HINTS):
            continue
        results.append(JobPosting(
            company=company,
            title=(j.get("title") or "").strip(),
            location=loc,
            url=j.get("absolute_url", ""),
            source="greenhouse",
            posted_date=(j.get("updated_at") or "")[:10] or None,
            posted_raw=j.get("updated_at", ""),
            description="",
            job_id=str(j.get("id", "")),
        ))
    return results
