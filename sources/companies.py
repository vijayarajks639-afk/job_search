"""
Registry of Workday "seed" sources — deterministic, free, exactly-dated postings
used to prime the agentic search step. Only companies with a verified, queryable
Workday endpoint live here. Everything else is handled by web search in the agent.

Workday country facet ids are global constants across tenants; India is reused below.
Add a new seed by appending a dict with a confirmed host/tenant/site.
"""

# Global Workday country facet id for India (verified identical across tenants).
INDIA_FACET = "c4f78be1a8f14da0ab49ce1162348a5e"

WORKDAY_SEEDS = [
    {
        # Verified June 2026: ~46 India roles, all Bengaluru (Manyata Tech Park).
        "company": "Commonwealth Bank (CBA)",
        "host": "cba.wd3.myworkdayjobs.com",
        "tenant": "cba",
        "site": "CommBank_Careers",
        "applied_facets": {"locationCountry": [INDIA_FACET]},
    },
    # The Standard: Workday exists but rejects the India facet (no India postings
    # there). Their India GCC (StanCorp Global) hires via Darwinbox instead — see
    # DARWINBOX_SEEDS below.
]

DARWINBOX_SEEDS = [
    {
        # Verified June 2026: 53 India roles (Bengaluru), public JSON, no auth.
        "company": "The Standard (Standard India)",
        "host": "stancorpglobal.darwinbox.in",
        "company_id": "main",
    },
]
