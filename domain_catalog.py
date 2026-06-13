"""
Domain-to-company catalog for the job-search pipeline.

Each domain maps to a curated list of top India employers / GCCs (Global
Capability Centres) known to hire for that domain. The list is **curated, not an
official ranking** — compiled (June 2026) from published "best workplaces / top
companies / top GCC" lists (Great Place To Work India, LinkedIn Top Companies,
AmbitionBox ABECA, Glassdoor) plus domain knowledge. It is **static data** — no
runtime API calls, no scraping. Companies are ordered roughly by prominence so
the first few are sensible defaults; names are kept plain so the Adzuna `what=`
search matches their job-board display names.

Refresh manually when the annual rankings update. ~40 companies per domain; many
appear in more than one domain (Amazon, Walmart, Honeywell, Bosch, …) — that's
expected.
"""

from __future__ import annotations

DOMAINS: dict[str, dict] = {

    "IT & Data Engineering": {
        "description": (
            "Software engineering, data platforms, cloud, AI/ML, DevOps, "
            "analytics, enterprise architecture — BFSI and tech GCCs in India."
        ),
        "companies": [
            "JPMorgan Chase", "Goldman Sachs", "Morgan Stanley", "Wells Fargo",
            "HSBC", "Barclays", "Citi", "Deutsche Bank", "Standard Chartered",
            "American Express", "Amazon", "Microsoft", "Google", "Adobe",
            "Salesforce", "ServiceNow", "SAP", "Oracle", "NVIDIA", "Intel",
            "Cisco", "Qualcomm", "VMware", "Walmart Global Tech", "Target",
            "Lowe's", "Tesco", "PayPal", "Uber", "Optum", "Mastercard", "Visa",
            "S&P Global", "LSEG", "Thomson Reuters", "Experian",
            "Fidelity Investments", "BlackRock", "Shell", "Bosch","NatWest", "Schroders", "abrdn", "Prudential", "Aviva", "Tata Consultancy Services",
        ],
    },

    "Banking & Financial Services": {
        "description": (
            "Finance, risk, compliance, treasury, investment banking, credit, "
            "payments — the business side of financial institutions."
        ),
        "companies": [
            "JPMorgan Chase", "Goldman Sachs", "Morgan Stanley",
            "Bank of America", "Wells Fargo", "Citi", "HSBC", "Barclays",
            "Deutsche Bank", "Standard Chartered", "UBS", "BNP Paribas",
            "Societe Generale", "Nomura", "Macquarie", "BlackRock",
            "State Street", "Northern Trust", "Fidelity Investments",
            "American Express", "Mastercard", "Visa", "PayPal", "S&P Global",
            "Moody's", "LSEG", "ICICI Bank", "HDFC Bank", "Axis Bank",
            "Kotak Mahindra Bank", "State Bank of India", "Bajaj Finance",
            "Mahindra Finance", "Shriram Finance", "Lloyds Banking Group",
            "NatWest", "Schroders", "abrdn", "Prudential", "Aviva", "Tata Consultancy Services",
        ],
    },

    "Healthcare & Life Sciences": {
        "description": (
            "Medical devices, pharmaceuticals, clinical operations, health IT, "
            "biotech — MNC captives and GCCs in India."
        ),
        "companies": [
            "Philips", "Abbott", "AstraZeneca", "Novartis", "Medtronic",
            "GE Healthcare", "Siemens Healthineers", "Johnson & Johnson",
            "Roche", "Sanofi", "Pfizer", "Merck", "Eli Lilly",
            "Bristol Myers Squibb", "GSK", "Novo Nordisk", "Bayer",
            "Boston Scientific", "Stryker", "Baxter International",
            "Becton Dickinson", "Fresenius Kabi", "Thermo Fisher Scientific",
            "Agilent Technologies", "Danaher", "Cytiva", "Waters Corporation",
            "IQVIA", "Parexel", "ICON plc", "Labcorp", "Syngene", "Biocon",
            "Cipla", "Sun Pharma", "Dr Reddy's", "Zoetis",
            "Edwards Lifesciences", "Cardinal Health", "Teleflex",
        ],
    },

    "Automotive & Manufacturing": {
        "description": (
            "Automotive engineering, embedded systems, ADAS, EV, manufacturing "
            "technology, industrial automation — MNC captives in India."
        ),
        "companies": [
            "Bosch", "Mercedes-Benz R&D India", "BMW TechWorks",
            "Continental", "ZF", "Schaeffler", "Harman", "Aptiv", "BorgWarner",
            "Valeo", "Knorr-Bremse", "Cummins", "Caterpillar", "John Deere",
            "Eaton", "Parker Hannifin", "Emerson", "Rockwell Automation",
            "Honeywell", "Mahindra", "Tata Motors", "Tata Technologies",
            "Ashok Leyland", "Maruti Suzuki", "Toyota Kirloskar",
            "Hyundai Motor", "Volvo Group", "Daimler Truck",
            "Renault Nissan Technology", "Hero MotoCorp", "Bajaj Auto",
            "TVS Motor", "Magna", "Lear", "Dana", "Visteon", "Marelli",
            "Forvia", "Cyient", "L&T Technology Services",
        ],
    },

    "Telecom & Networking": {
        "description": (
            "Telecommunications, 5G, network engineering, wireless, optical "
            "networking — MNC R&D and GCC centres in India."
        ),
        "companies": [
            "Ericsson", "Nokia", "Qualcomm", "Cisco", "Juniper Networks",
            "Samsung R&D", "Broadcom", "Marvell", "CommScope", "Ciena",
            "Keysight Technologies", "Arista Networks", "Infinera", "Viavi",
            "Spirent", "NetScout", "Ribbon Communications", "Mavenir",
            "Radisys", "Tejas Networks", "Sterlite Technologies", "HFCL",
            "Reliance Jio", "Bharti Airtel", "Vodafone Idea",
            "Tata Communications", "Verizon", "AT&T", "T-Mobile",
            "Deutsche Telekom", "Orange", "BT Group", "Colt Technology",
            "Subex", "Route Mobile", "Tanla", "Sinch", "Jabil",
            "Extreme Networks", "Calix",
        ],
    },

    "Energy & Utilities": {
        "description": (
            "Oil & gas, power, renewables, energy engineering, industrial "
            "process control — MNC captives and Indian majors."
        ),
        "companies": [
            "Shell", "BP", "Chevron", "ExxonMobil", "TotalEnergies",
            "Schlumberger", "Baker Hughes", "Halliburton", "Honeywell", "ABB",
            "Siemens Energy", "GE Vernova", "Schneider Electric", "Eaton",
            "Emerson", "Wood", "Worley", "TechnipFMC", "Reliance Industries",
            "Adani Group", "Tata Power", "NTPC", "ONGC", "Indian Oil", "BPCL",
            "HPCL", "GAIL", "Vedanta", "JSW Energy", "ReNew", "Greenko",
            "Linde", "Air Products", "Petronas", "Saudi Aramco", "McDermott",
            "Fluor", "Bechtel", "KBR", "Cairn Oil & Gas",
        ],
    },

    "FMCG, Retail & Consumer": {
        "description": (
            "Consumer goods, retail, supply chain, marketing analytics, "
            "e-commerce technology — MNC captives and Indian leaders."
        ),
        "companies": [
            "Unilever", "Procter & Gamble", "Nestle", "PepsiCo", "Coca-Cola",
            "Colgate-Palmolive", "Mondelez", "Kraft Heinz", "Kimberly-Clark",
            "Reckitt", "L'Oreal", "Estee Lauder", "Mars", "Diageo",
            "AB InBev", "ITC", "Hindustan Unilever", "Britannia", "Dabur",
            "Marico", "Godrej Consumer", "Tata Consumer", "Amazon",
            "Flipkart", "Walmart Global Tech", "Target", "Tesco", "Lowe's",
            "IKEA", "H&M", "Decathlon", "Reliance Retail", "Swiggy", "Zomato",
            "Nykaa", "Myntra", "Shoppers Stop", "Lulu Group", "Meesho",
            "Blinkit",
        ],
    },

    "Engineering & Industrial Technology": {
        "description": (
            "Mechanical, aerospace, defence, industrial software, EPC — "
            "engineering R&D captives and services GCCs in India."
        ),
        "companies": [
            "GE Aerospace", "Rolls-Royce", "Pratt & Whitney", "Boeing",
            "Airbus", "Safran", "Collins Aerospace", "Honeywell Aerospace",
            "L3Harris", "Thales", "BAE Systems", "Siemens Digital Industries",
            "ABB", "Schneider Electric", "Emerson", "Rockwell Automation",
            "Dassault Systemes", "Ansys", "PTC", "Autodesk", "Bentley Systems",
            "Hexagon", "AECOM", "WSP", "Jacobs", "Fluor", "Wood", "Worley",
            "Bechtel", "KBR", "L&T Technology Services", "Tata Technologies",
            "Cyient", "Quest Global", "HCLTech Engineering",
            "Capgemini Engineering", "Alten", "Tata Elxsi", "KPIT", "Tata Consultancy Services",
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
