"""
Generic Oracle Cloud Recruiting (ORC) careers connector.

Oracle-hosted career sites expose a public REST endpoint:

    GET https://<host>/hcmRestApi/resources/latest/recruitingCEJobRequisitions
        ?onlyData=true&finder=findReqs;siteNumber=<site>,keyword="India",
         sortBy=POSTING_DATES_DESC,limit=<n>,offset=<n>

Response: {"items": [{"TotalJobsCount": N, "requisitionList": [{Id, Title,
PostedDate (ISO), PrimaryLocation, ShortDescriptionStr, ...}]}]}.
Public posting URL:
    https://<host>/hcmUI/CandidateExperience/en/sites/<site>/job/<Id>
Verified June 2026 against jpmc.fa.oraclecloud.com (siteNumber CX_1001).
"""

from __future__ import annotations

import requests

import config
from sources.base import JobPosting


def fetch(company: str, host: str, site_number: str,
          keyword: str = "India", max_results: int = 200) -> list[JobPosting]:
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    results: list[JobPosting] = []
    offset, page_size = 0, 50

    while offset < max_results:
        finder = (f"findReqs;siteNumber={site_number},"
                  f'keyword=%22{keyword}%22,'
                  f"sortBy=POSTING_DATES_DESC,limit={page_size},offset={offset}")
        # expand is required — without it requisitionList comes back empty
        # even though TotalJobsCount is populated (verified June 2026).
        url = (f"https://{host}/hcmRestApi/resources/latest/"
               f"recruitingCEJobRequisitions?onlyData=true"
               f"&expand=requisitionList.secondaryLocations&finder={finder}")
        resp = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            break

        reqs = items[0].get("requisitionList", [])
        if not reqs:
            break

        for r in reqs:
            req_id = r.get("Id", "")
            results.append(JobPosting(
                company=company,
                title=(r.get("Title") or "").strip(),
                location=(r.get("PrimaryLocation") or "").strip(),
                url=(f"https://{host}/hcmUI/CandidateExperience/en/sites/"
                     f"{site_number}/job/{req_id}"),
                source="oracle_orc",
                posted_date=(r.get("PostedDate") or "")[:10] or None,
                posted_raw=r.get("PostedDate", ""),
                description=(r.get("ShortDescriptionStr") or "")[:600],
                job_id=str(req_id),
            ))

        offset += page_size
        if offset >= items[0].get("TotalJobsCount", 0):
            break

    return results
