"""
Resume-driven domain detection for the public cloud demo — no LLM.

The local pipeline detects domain with a Claude headless call (agent_run.
detect_domain). That cannot run on Streamlit Community Cloud, so the demo uses
a transparent keyword heuristic: score the resume text against per-domain
keyword lists, rank, and report confidence from the margin between the top two
domains. Good enough to preselect companies; the visitor can always adjust.

PRIVACY: callers must pass resume text already extracted in memory. Nothing in
this module writes the text to disk or logs it — only the detected domain name
may be logged by the caller.
"""

from __future__ import annotations

import io
import re

from domain_catalog import DOMAINS

# Phrase keywords (multi-word) score 2, single words score 1.
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "IT & Data Engineering": [
        "data platform", "data engineering", "data warehouse", "data lake",
        "lakehouse", "data mesh", "data governance", "machine learning",
        "etl", "spark", "kafka", "hadoop", "databricks", "snowflake",
        "python", "sql", "aws", "azure", "gcp", "cloud", "devops",
        "microservices", "api", "architect", "kubernetes", "airflow",
        # Senior / leadership & enterprise wording (resumes light on raw tools)
        "engineering manager", "engineering lead", "solution architect",
        "enterprise architecture", "technical architect", "data architect",
        "delivery management", "agile", "scrum", "ci/cd", "data modeling",
        "data modelling", "data quality", "big data", "informatica",
        "teradata", "tableau", "power bi", "qlik", "oracle", "sql server",
        "java", "scala", "rest api", "platform modernization",
        "analytics", "business intelligence", "mlops",
    ],
    "Banking & Financial Services": [
        "credit risk", "regulatory reporting", "investment banking",
        "wealth management", "capital markets", "anti money laundering",
        "banking", "basel", "compliance", "treasury", "trading", "payments",
        "aml", "kyc", "lending", "mortgage", "insurance", "actuarial",
        "financial services", "asset management", "risk management",
        "market risk", "operational risk", "finance transformation",
        "reconciliation", "settlements", "fraud", "bfsi",
    ],
    "Healthcare & Life Sciences": [
        "clinical trials", "medical device", "life sciences", "regulatory affairs",
        "clinical", "pharma", "pharmaceutical", "healthcare", "fda", "gxp",
        "patient", "biotech", "genomics", "diagnostics",
    ],
    "Automotive & Manufacturing": [
        "embedded systems", "industrial automation", "supply chain manufacturing",
        "automotive", "autosar", "adas", "powertrain", "vehicle", "ev",
        "manufacturing", "plc", "mechatronics", "can bus", "iso 26262",
    ],
    "Telecom & Networking": [
        "network engineering", "optical networking", "packet core",
        "telecom", "5g", "lte", "ran", "wireless", "voip", "sip", "ericsson",
        "nokia", "routing", "switching",
    ],
    "Energy & Utilities": [
        "oil and gas", "power generation", "process control",
        "energy", "renewable", "scada", "drilling", "refinery", "utility",
        "petroleum", "turbine", "grid",
    ],
    "FMCG, Retail & Consumer": [
        "consumer goods", "supply chain retail", "e-commerce",
        "retail", "fmcg", "cpg", "merchandising", "category management",
        "trade marketing", "store operations", "omnichannel",
    ],
    "Engineering & Industrial Technology": [
        "structural analysis", "computational fluid dynamics",
        "aerospace", "defence", "defense", "avionics", "cad", "cae",
        "mechanical design", "stress analysis", "composites",
    ],
}


# Bound work even though Streamlit caps the upload at 5 MB (.streamlit/config.toml):
# defence in depth against a small-but-pathological PDF.
_MAX_BYTES = 6_000_000
_MAX_PDF_PAGES = 30
_MAX_TEXT_CHARS = 40_000


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from an uploaded PDF/TXT, fully in memory (bounded)."""
    file_bytes = file_bytes[:_MAX_BYTES]
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = reader.pages[:_MAX_PDF_PAGES]
        text = "\n".join((page.extract_text() or "") for page in pages)
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
    return text[:_MAX_TEXT_CHARS]


def detect(resume_text: str) -> dict:
    """
    Returns {"domain", "confidence", "matched_keywords", "companies", "scores"}.
    confidence: high (clear winner), medium (close second), low (few hits).
    """
    text = re.sub(r"\s+", " ", resume_text.lower())
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}
    for domain, kws in DOMAIN_KEYWORDS.items():
        hits = []
        score = 0
        for kw in kws:
            if kw in text:
                hits.append(kw)
                score += 2 if " " in kw else 1
        scores[domain] = score
        matched[domain] = hits

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    top_domain, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_score == 0:
        confidence = "none"          # no signal at all (scanned/empty PDF)
    elif top_score < 3:
        confidence = "low"           # weak, but still the best guess — KEEP it
    elif top_score >= second_score * 1.5:
        confidence = "high"
    else:
        confidence = "medium"

    return {
        "domain": top_domain,
        "confidence": confidence,
        "matched_keywords": matched[top_domain][:8],
        "companies": DOMAINS[top_domain]["companies"],
        "scores": {d: s for d, s in ranked[:3]},
    }
