"""
Generic Eightfold AI careers connector.

Eightfold-powered career sites expose a public JSON endpoint:

    GET https://<host>/api/apply/v2/jobs?domain=<domain>&location=India&num=100&start=0

Response: {"count": N, "positions": [{name, location, canonicalPositionUrl,
t_create (epoch seconds), ...}]}. Verified June 2026 against hsbc.eightfold.ai.
"""

from __future__ import annotations

from datetime import datetime, timezone

import requests

import config
from sources.base import JobPosting


def fetch(company: str, host: str, domain: str,
          location: str = "India", max_results: int = 200) -> list[JobPosting]:
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    results: list[JobPosting] = []
    start, page_size = 0, 100

    while start < max_results:
        url = (f"https://{host}/api/apply/v2/jobs?"
               f"domain={domain}&location={location}&num={page_size}&start={start}")
        resp = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        positions = data.get("positions", [])
        if not positions:
            break

        for p in positions:
            t_create = p.get("t_create") or p.get("t_update")
            posted = (datetime.fromtimestamp(t_create, tz=timezone.utc).date().isoformat()
                      if isinstance(t_create, (int, float)) and t_create > 0 else None)
            results.append(JobPosting(
                company=company,
                title=(p.get("name") or "").strip(),
                location=(p.get("location") or "").strip(),
                url=p.get("canonicalPositionUrl", "") or f"https://{host}",
                source="eightfold",
                posted_date=posted,
                posted_raw=str(t_create or ""),
                description=(p.get("job_description") or "")[:600],
                job_id=str(p.get("id", "")),
            ))

        # The API may cap the page below the requested num (HSBC returns 20
        # per page regardless) — advance by what was actually returned.
        start += len(positions)
        if start >= data.get("count", 0):
            break

    return results
