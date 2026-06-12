"""
Generic SmartRecruiters careers connector.

Public unauthenticated postings API:

    GET https://api.smartrecruiters.com/v1/companies/<company_id>/postings
        ?country=in&limit=100&offset=0

Response: {"totalFound": N, "content": [{id, name, releasedDate,
location: {city, country, fullLocation?}, company: {identifier}, ...}]}.
Public posting URL: https://jobs.smartrecruiters.com/<identifier>/<id>.
Verified June 2026 against visa / experian / servicenow.
"""

from __future__ import annotations

import requests

import config
from sources.base import JobPosting

API = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"


def fetch(company: str, company_id: str, country: str = "in",
          max_results: int = 200) -> list[JobPosting]:
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    results: list[JobPosting] = []
    offset, page_size = 0, 100

    while offset < max_results:
        resp = requests.get(
            API.format(company_id=company_id),
            params={"country": country, "limit": page_size, "offset": offset},
            headers=headers, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        content = data.get("content", [])
        if not content:
            break

        for p in content:
            loc = p.get("location") or {}
            loc_text = ", ".join(x for x in (loc.get("city"), loc.get("region"),
                                             loc.get("country")) if x)
            identifier = (p.get("company") or {}).get("identifier", company_id)
            posting_id = p.get("id", "")
            results.append(JobPosting(
                company=company,
                title=(p.get("name") or "").strip(),
                location=loc_text,
                url=f"https://jobs.smartrecruiters.com/{identifier}/{posting_id}",
                source="smartrecruiters",
                posted_date=(p.get("releasedDate") or "")[:10] or None,
                posted_raw=p.get("releasedDate", ""),
                description="",
                job_id=str(posting_id),
            ))

        offset += page_size
        if offset >= data.get("totalFound", 0):
            break

    return results
