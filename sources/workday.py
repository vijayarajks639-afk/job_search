"""
Generic Workday careers connector.

Most enterprise Workday career sites expose a JSON search endpoint:

    POST https://<host>/wday/cxs/<tenant>/<site>/jobs
    body: {"appliedFacets": {...}, "limit": 20, "offset": 0, "searchText": "..."}

Response contains `jobPostings`, each with title, externalPath, locationsText,
postedOn (a relative string), and bulletFields. The public job URL is
`https://<host>/<site>` + externalPath.

This connector is intentionally tolerant: site structures vary, so it defends
against missing fields and returns whatever it can parse.
"""

from __future__ import annotations

import requests

import config
from sources.base import JobPosting, parse_relative_posted


def fetch(company: str, host: str, tenant: str, site: str,
          search_text: str = "", applied_facets: dict | None = None,
          max_pages: int = 5, page_size: int = 20) -> list[JobPosting]:
    """
    Pull postings for one Workday site. Raises requests exceptions on hard
    network/HTTP failure so the orchestrator can record the source as failed.
    """
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    public_base = f"https://{host}/{site}"
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    results: list[JobPosting] = []
    for page in range(max_pages):
        body = {
            "appliedFacets": applied_facets or {},
            "limit": page_size,
            "offset": page * page_size,
            "searchText": search_text,
        }
        resp = requests.post(api, json=body, headers=headers,
                             timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        postings = data.get("jobPostings", [])
        if not postings:
            break

        for jp in postings:
            ext = jp.get("externalPath", "") or ""
            url = public_base + ext if ext else public_base
            posted_raw = jp.get("postedOn", "") or ""
            results.append(JobPosting(
                company=company,
                title=(jp.get("title", "") or "").strip(),
                location=(jp.get("locationsText", "") or "").strip(),
                url=url,
                source="workday",
                posted_date=parse_relative_posted(posted_raw),
                posted_raw=posted_raw,
                description=" ".join(jp.get("bulletFields", []) or []),
                job_id=(jp.get("bulletFields", [""]) or [""])[0],
            ))

        total = data.get("total", 0)
        if (page + 1) * page_size >= total:
            break

    return results
