"""
Adzuna aggregator connector — fallback for companies without a direct ATS
connector.

Adzuna indexes job boards and company career sites and exposes a free search
API (https://developer.adzuna.com/, free tier ~250 calls/day). India endpoint:

    GET https://api.adzuna.com/v1/api/jobs/in/search/1
        ?app_id=...&app_key=...&what=<company+keywords>&results_per_page=20

IMPORTANT: Adzuna's `company=` parameter validates against their internal
company registry and returns HTTP 400 for companies not registered by that
exact name. We instead use `what="{company}"` (keyword search) and post-filter
results to jobs whose `company.display_name` contains the target name.

Postings carry a real `created` timestamp, so unlike web-search snippets these
are dated. Still aggregator data — a posting can lag the company site by a day
or two, hence the dashboard shows a "verify on site" badge for source=adzuna.

Requires config.ADZUNA_APP_ID / ADZUNA_APP_KEY (env vars); the orchestrator
skips this connector entirely when they are unset.
"""

from __future__ import annotations

import requests

import config
from sources.base import JobPosting

API = "https://api.adzuna.com/v1/api/jobs/in/search/1"

# Maps our canonical company names to how they appear in Adzuna's company
# database. Adzuna's `what=` search is keyword-based so these aliases improve
# post-filter hit rates. Verified June 2026.
_ADZUNA_NAME_ALIASES: dict[str, str] = {
    "Citi":           "Citigroup",
    "UBS":            "UBS Group",
    "Macquarie":      "Macquarie Group",
    "Nomura":         "Nomura",           # exact match works
    "BNP Paribas":    "BNP Paribas",
    "Morgan Stanley": "Morgan Stanley",
}


def fetch(company: str, what: str = "", max_days_old: int | None = None,
          results: int = 20) -> list[JobPosting]:
    """
    Pull recent India postings for one company.

    Uses `what=<company> <keywords>` (free-text) instead of `company=` because
    Adzuna's company filter validates against its internal database and returns
    HTTP 400 for companies not registered under that exact name.

    Post-filters results to jobs whose company.display_name contains either the
    canonical name or its Adzuna alias to reduce false positives.

    Raises requests exceptions on hard failure so the orchestrator records it.
    """
    if not config.AGGREGATOR_ENABLED:
        return []

    # Use Adzuna's registered company name for the what= query when available
    adzuna_name = _ADZUNA_NAME_ALIASES.get(company, company)

    # Build the what query: company name + optional role keywords
    what_parts = [adzuna_name]
    if what:
        what_parts.append(what)
    what_query = " ".join(what_parts)

    params = {
        "app_id": config.ADZUNA_APP_ID,
        "app_key": config.ADZUNA_APP_KEY,
        "what": what_query,
        "results_per_page": results,
    }
    if max_days_old:
        params["max_days_old"] = max_days_old

    resp = requests.get(API, params=params,
                        headers={"User-Agent": config.USER_AGENT},
                        timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    company_lower  = company.lower()
    alias_lower    = _ADZUNA_NAME_ALIASES.get(company, company).lower()
    out: list[JobPosting] = []
    for r in data.get("results", []):
        # Post-filter: keep only jobs actually at this company (or its alias)
        co_name = (r.get("company") or {}).get("display_name", "")
        co_lower = co_name.lower()
        canonical_match = company_lower in co_lower or co_lower in company_lower
        alias_match     = alias_lower   in co_lower or co_lower in alias_lower
        if not (canonical_match or alias_match):
            continue

        created = (r.get("created") or "")[:10]  # "2026-06-10T..." -> ISO date
        title = (r.get("title") or "").replace("<strong>", "").replace("</strong>", "").strip()
        out.append(JobPosting(
            company=co_name or company,
            title=title,
            location=(r.get("location") or {}).get("display_name", ""),
            url=r.get("redirect_url", ""),
            source="adzuna",
            posted_date=created or None,
            posted_raw=r.get("created", ""),
            description=(r.get("description") or "")[:600],
            job_id=str(r.get("id", "")),
        ))
    return out
