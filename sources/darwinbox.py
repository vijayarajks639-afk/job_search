"""
Generic Darwinbox careers connector.

Darwinbox-hosted career sites expose a public JSON listing endpoint:

    POST https://<host>/ms/candidateapi/job/alljobs?companyId=main
    body: {"companyId":"main","page":1,"sort_option":"new","limit":20}
    -> {"status":"success","data":[ {job}, ... ]}

Job detail pages: https://<host>/ms/candidatev2/main/careers/jobDetails/<id>

Verified June 2026 against The Standard (StanCorp Global, stancorpglobal.darwinbox.in)
— 53 India roles, no auth required. Reusable for any Darwinbox tenant by host.
"""

from __future__ import annotations

import html
import re
import time

import requests

import config
from sources.base import JobPosting

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_posted(job: dict) -> str | None:
    # Prefer created_on ISO; fall back to 'posted_on' like "9-Jun-2026".
    iso = job.get("created_on")
    if iso:
        try:
            from datetime import datetime
            return datetime.strptime(iso[:10], "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    posted = job.get("posted_on")
    if posted:
        from datetime import datetime
        try:
            return datetime.strptime(posted, "%d-%b-%Y").date().isoformat()
        except ValueError:
            return None
    return None


def _location(job: dict) -> str:
    arr = job.get("officelocations_without_area")
    if isinstance(arr, list) and arr:
        return "; ".join(arr)
    return (job.get("officelocation_show_arr") or job.get("country") or "").strip()


def fetch(company: str, host: str, company_id: str = "main",
          max_pages: int = 10, page_size: int = 20) -> list[JobPosting]:
    """Pull all postings for one Darwinbox site. Raises on hard failure."""
    api = f"https://{host}/ms/candidateapi/job/alljobs?companyId={company_id}"
    detail = f"https://{host}/ms/candidatev2/main/careers/jobDetails/"

    s = requests.Session()
    s.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": f"https://{host}",
        "Referer": f"https://{host}/ms/candidatev2/main/careers/allJobs",
        "Accept-Language": "en",
    })

    results: list[JobPosting] = []
    for page in range(1, max_pages + 1):
        body = {"companyId": company_id, "page": page,
                "sort_option": "new", "limit": page_size}
        data = None
        for attempt in range(3):  # Cloudflare occasionally challenges a call
            resp = s.post(api, json=body, timeout=config.REQUEST_TIMEOUT)
            if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
                data = resp.json()
                break
            time.sleep(1.5)
        if not data:
            resp.raise_for_status()  # surface the last failure to the orchestrator
            break

        jobs = data.get("data", [])
        if not jobs:
            break

        for j in jobs:
            jid = j.get("id", "")
            results.append(JobPosting(
                company=company,
                title=(j.get("title") or j.get("designation_display_name") or "").strip(),
                location=_location(j),
                url=detail + jid if jid else f"https://{host}/ms/candidatev2/main/careers/allJobs",
                source="darwinbox",
                posted_date=_parse_posted(j),
                posted_raw=j.get("posted_on", "") or "",
                description=_strip_html(j.get("jd") or j.get("jd_summary") or "")[:4000],
                job_id=jid,
            ))

        if len(jobs) < page_size:
            break

    return results
