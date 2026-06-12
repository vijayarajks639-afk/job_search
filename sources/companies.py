"""
Unified registry of companies with a verified direct ATS connector.

Every entry was confirmed live by scripts/probe_ats.py (June 2026) — the
endpoint responded with real India postings. Companies NOT listed here are
covered by the Adzuna aggregator (if enabled) and agent web search.

To add a company: run `python scripts/probe_ats.py --company "Name"` and paste
the confirmed entry below.
"""

# Global Workday country facet id for India (verified identical across tenants).
INDIA_FACET = "c4f78be1a8f14da0ab49ce1162348a5e"

_WD_INDIA = {"locationCountry": [INDIA_FACET]}

CONNECTED_COMPANIES: list[dict] = [
    # ── Workday ───────────────────────────────────────────────────────────────
    {"company": "Commonwealth Bank (CBA)", "platform": "workday",
     "host": "cba.wd3.myworkdayjobs.com", "tenant": "cba",
     "site": "CommBank_Careers", "applied_facets": _WD_INDIA},
    {"company": "BlackRock", "platform": "workday",
     "host": "blackrock.wd1.myworkdayjobs.com", "tenant": "blackrock",
     "site": "BlackRock_Professional", "applied_facets": _WD_INDIA},
    {"company": "LSEG (London Stock Exchange Group)", "platform": "workday",
     "host": "lseg.wd3.myworkdayjobs.com", "tenant": "lseg",
     "site": "careers", "applied_facets": _WD_INDIA},
    {"company": "Adobe", "platform": "workday",
     "host": "adobe.wd5.myworkdayjobs.com", "tenant": "adobe",
     "site": "external_experienced", "applied_facets": _WD_INDIA},

    # ── Darwinbox ─────────────────────────────────────────────────────────────
    {"company": "The Standard (Standard India)", "platform": "darwinbox",
     "host": "stancorpglobal.darwinbox.in", "company_id": "main"},

    # ── Eightfold ─────────────────────────────────────────────────────────────
    {"company": "HSBC", "platform": "eightfold",
     "host": "hsbc.eightfold.ai", "domain": "hsbc.com"},

    # ── Oracle Cloud Recruiting ───────────────────────────────────────────────
    {"company": "JPMorgan Chase", "platform": "oracle_orc",
     "host": "jpmc.fa.oraclecloud.com", "site_number": "CX_1001"},

    # ── SmartRecruiters ───────────────────────────────────────────────────────
    {"company": "Visa", "platform": "smartrecruiters", "company_id": "visa"},
    {"company": "Experian", "platform": "smartrecruiters", "company_id": "experian"},
    {"company": "ServiceNow", "platform": "smartrecruiters", "company_id": "servicenow"},
    {"company": "Legal & General", "platform": "smartrecruiters",
     "company_id": "legalandgeneral"},

    # ── Greenhouse ────────────────────────────────────────────────────────────
    {"company": "Moody's", "platform": "greenhouse", "board_token": "mco"},
]


def connector_for(company: str) -> dict | None:
    """Registry entry for a company name (substring match both ways)."""
    co = company.strip().lower()
    for entry in CONNECTED_COMPANIES:
        name = entry["company"].lower()
        if co in name or name in co:
            return entry
    return None


def split_by_coverage(companies: list[str]) -> tuple[list[str], list[str]]:
    """(companies with a direct connector, companies without)."""
    covered, uncovered = [], []
    for c in companies:
        (covered if connector_for(c) else uncovered).append(c)
    return covered, uncovered


# ── Backward-compatible aliases (old fetch_jobs.py shape) ─────────────────────
WORKDAY_SEEDS = [e for e in CONNECTED_COMPANIES if e["platform"] == "workday"]
DARWINBOX_SEEDS = [e for e in CONNECTED_COMPANIES if e["platform"] == "darwinbox"]
