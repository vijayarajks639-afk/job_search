"""
Domain-to-company catalog for the job-search pipeline.

Each domain entry maps to a curated list of India GCCs / captive centres that
are known to hire for that domain. The agent uses this to focus web searches
rather than the user having to manually pick companies.

Add or remove companies freely — the agent adapts automatically.
"""

from __future__ import annotations

DOMAINS: dict[str, dict] = {

    "IT & Data Engineering": {
        "description": (
            "Software engineering, data platforms, cloud, AI/ML, DevOps, "
            "analytics, enterprise architecture — typically for BFSI and tech GCCs."
        ),
        "companies": [
            # BFSI GCCs (data/tech teams)
            "ANZ", "Commonwealth Bank (CBA)", "The Standard (Standard India)",
            "JPMorgan Chase", "Goldman Sachs", "Morgan Stanley", "Bank of America",
            "HSBC", "Barclays", "Deutsche Bank", "UBS", "Citi",
            "Macquarie", "BlackRock", "State Street", "Northern Trust",
            "Nomura", "Societe Generale", "BNP Paribas",
            # Payments & FinTech
            "Mastercard", "Visa", "American Express", "Fidelity Investments",
            "S&P Global", "LSEG (London Stock Exchange Group)", "Moody's",
            "Experian", "Thomson Reuters",
            # Tech & Retail
            "Walmart Global Tech", "Target", "Tesco", "Lowe's", "NVIDIA",
            "Salesforce", "ServiceNow", "SAP Labs", "Adobe",
            "Microsoft IDC", "Optum / UnitedHealth",
            # Upcoming GCCs
            "Lloyds Banking Group", "M&G / Prudential", "Allianz Technology",
            "Zurich Insurance", "Aviva", "Legal & General", "Schroders", "abrdn",
        ],
    },

    "Banking & Financial Services": {
        "description": (
            "Finance, risk, compliance, treasury, investment banking, credit — "
            "roles on the business side of financial institutions."
        ),
        "companies": [
            "JPMorgan Chase", "Goldman Sachs", "Morgan Stanley", "Bank of America",
            "HSBC", "Barclays", "Deutsche Bank", "UBS", "Citi",
            "ANZ", "Commonwealth Bank (CBA)", "Macquarie", "BlackRock",
            "State Street", "Northern Trust", "Nomura", "Societe Generale",
            "BNP Paribas", "Fidelity Investments", "S&P Global", "Moody's",
            "Lloyds Banking Group", "Schroders", "abrdn",
        ],
    },

    "Healthcare & Life Sciences": {
        "description": (
            "Medical devices, pharmaceuticals, clinical operations, health IT, "
            "biotech — MNC captives and GCCs in India."
        ),
        "companies": [
            "Philips India (Bengaluru)",
            "Abbott India",
            "AstraZeneca India (Bengaluru)",
            "Novartis India (Hyderabad)",
            "Medtronic India (Hyderabad)",
            "GE Healthcare India (Bengaluru)",
            "Siemens Healthineers India",
            "Johnson & Johnson India",
            "Baxter International India",
            "Danaher India (Bengaluru)",
            "Becton Dickinson (BD) India",
            "Fresenius Kabi India",
            "Roche India",
            "Sanofi India",
            "MSD (Merck) India",
            "Eli Lilly India",
            "Bristol Myers Squibb India",
            "Pfizer India",
            "Thermo Fisher Scientific India",
            "Agilent Technologies India",
        ],
    },

    "Automotive & Manufacturing": {
        "description": (
            "Automotive engineering, embedded systems, ADAS, EV, manufacturing "
            "technology, industrial automation — MNC captives in India."
        ),
        "companies": [
            "Bosch India (Bengaluru)",
            "Continental India (Bengaluru)",
            "Schaeffler India (Pune)",
            "ZF India (Pune)",
            "Harman International India (Bengaluru)",
            "Aptiv India (Hyderabad)",
            "BorgWarner India (Chennai)",
            "Knorr-Bremse India (Bengaluru)",
            "Valeo India",
            "Mahindra Tech India",
            "Tata Technologies (Pune)",
            "Cummins India (Pune)",
            "Caterpillar India (Bengaluru, Chennai)",
            "John Deere India (Pune)",
            "Eaton India (Pune)",
            "Parker Hannifin India",
            "Emerson India",
            "Rockwell Automation India",
            "Toyota Kirloskar India",
            "Mercedes-Benz R&D India (Bengaluru)",
        ],
    },

    "Telecom & Networking": {
        "description": (
            "Telecommunications, 5G, network engineering, wireless, optical networking — "
            "MNC R&D and GCC centres in India."
        ),
        "companies": [
            "Ericsson India (Bengaluru, Chennai)",
            "Nokia India (Chennai, Bengaluru)",
            "Qualcomm India (Hyderabad, Bengaluru)",
            "Cisco India (Bengaluru)",
            "Juniper Networks India (Bengaluru)",
            "CommScope India (Bengaluru)",
            "Ciena India (Bengaluru)",
            "Keysight Technologies India",
            "Spirent India",
            "Ribbon Communications India",
            "Mavenir India",
            "Radisys India",
            "Jabil India",
            "Broadcom India (Bengaluru)",
            "Marvell India (Hyderabad)",
        ],
    },

    "Energy & Utilities": {
        "description": (
            "Oil & gas, power, renewables, energy engineering, "
            "industrial process control — MNC captives in India."
        ),
        "companies": [
            "Shell India (Bengaluru, Chennai)",
            "BP India (Pune)",
            "Chevron India (Bengaluru)",
            "Schlumberger (SLB) India",
            "Baker Hughes India (Bengaluru)",
            "Honeywell India (Bengaluru, Hyderabad)",
            "ABB India (Bengaluru)",
            "Siemens Energy India",
            "GE Power India (Bengaluru)",
            "Schneider Electric India",
            "Eaton India",
            "Doosan India",
            "Wood India",
            "Worley India",
            "TechnipFMC India",
        ],
    },

    "FMCG, Retail & Consumer": {
        "description": (
            "Consumer goods, retail, supply chain, marketing analytics, "
            "e-commerce technology — MNC captives in India."
        ),
        "companies": [
            "Unilever India (Mumbai, Bengaluru)",
            "Procter & Gamble India (Bengaluru)",
            "Nestle India (Gurgaon)",
            "PepsiCo India (Gurgaon, Hyderabad)",
            "Colgate-Palmolive India (Mumbai)",
            "Kimberly-Clark India",
            "Reckitt India (Hyderabad)",
            "Amazon India (Bengaluru, Hyderabad)",
            "Flipkart GCC (Bengaluru)",
            "Walmart Global Tech (Bengaluru)",
            "Target India (Bengaluru)",
            "Tesco India (Bengaluru)",
            "Lowe's India (Bengaluru)",
            "L'Oréal India",
            "Estée Lauder India",
        ],
    },

    "Engineering & Industrial Technology": {
        "description": (
            "Mechanical, civil, structural, aerospace, defence — engineering R&D "
            "captives and GCCs with India presence."
        ),
        "companies": [
            "GE Aerospace India (Bengaluru)",
            "Rolls-Royce India (Bengaluru)",
            "Pratt & Whitney India",
            "Boeing India (Bengaluru)",
            "Airbus India (Bengaluru)",
            "Safran India",
            "L3Harris India",
            "Thales India",
            "AECOM India",
            "WSP Global India",
            "Jacobs Engineering India",
            "Fluor India",
            "Wood India",
            "Ansys India (Pune)",
            "Dassault Systèmes India (Bengaluru)",
            "PTC India",
            "Siemens Digital Industries India",
        ],
    },
}

# Flat list of all companies across all domains (for fallback / full search).
ALL_COMPANIES: list[str] = sorted(
    {co for d in DOMAINS.values() for co in d["companies"]}
)


def companies_for_domain(domain: str) -> list[str]:
    """Return company list for a domain name (case-insensitive prefix match)."""
    domain_lower = domain.lower()
    for key, val in DOMAINS.items():
        if key.lower().startswith(domain_lower) or domain_lower in key.lower():
            return val["companies"]
    return ALL_COMPANIES
