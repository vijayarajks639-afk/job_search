"""
ATS endpoint discovery probe.

For each company in the catalog, tests the public unauthenticated JSON endpoint
patterns of the six common ATS platforms (Workday, Greenhouse, Lever,
SmartRecruiters, Oracle ORC, Eightfold) and reports which one responds with
valid postings — including an India job count where the API supports filtering.

This is a one-time discovery tool: paste the confirmed entries into
sources/companies.py CONNECTED_COMPANIES. Re-run whenever you add new companies
to the catalog.

Usage:
    python scripts/probe_ats.py                          # probe IT & Data Engineering domain
    python scripts/probe_ats.py --domain "Healthcare"    # probe another domain
    python scripts/probe_ats.py --company "Mastercard"   # probe a single company
    python scripts/probe_ats.py --workers 8
Output:
    console table + scripts/probe_results.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import domain_catalog
from sources.companies import INDIA_FACET

TIMEOUT = 8
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) job-probe/1.0",
      "Accept": "application/json"}

INDIA_HINTS = ("india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai",
               "mumbai", "gurgaon", "gurugram", "noida", "delhi")

# Manual slug aliases for companies whose obvious slug differs from their name.
ALIASES: dict[str, list[str]] = {
    "JPMorgan Chase":              ["jpmc", "jpmorganchase", "jpmorgan"],
    "Commonwealth Bank (CBA)":     ["cba", "commbank"],
    "The Standard (Standard India)": ["stancorpglobal", "standard"],
    "S&P Global":                  ["spgi", "spglobal"],
    "Northern Trust":              ["ntrs", "northerntrust"],
    "Thomson Reuters":             ["thomsonreuters", "tr"],
    "LSEG (London Stock Exchange Group)": ["lseg"],
    "Bank of America":             ["bankofamerica", "bofa", "baml"],
    "Morgan Stanley":              ["morganstanley", "ms"],
    "Goldman Sachs":               ["goldmansachs", "gs"],
    "Deutsche Bank":               ["deutschebank", "db"],
    "Societe Generale":            ["societegenerale", "socgen", "sgcib"],
    "BNP Paribas":                 ["bnpparibas", "bnp"],
    "American Express":            ["americanexpress", "amex", "aexp"],
    "Fidelity Investments":        ["fidelity", "fmr"],
    "Walmart Global Tech":         ["walmart", "walmartglobaltech"],
    "Optum / UnitedHealth":        ["optum", "unitedhealthgroup", "uhg"],
    "Microsoft IDC":               ["microsoft"],
    "SAP Labs":                    ["sap"],
    "LSEG":                        ["lseg"],
    "M&G / Prudential":            ["mandg", "prudential"],
    "Allianz Technology":          ["allianz", "allianztechnology"],
    "Legal & General":             ["legalandgeneral", "landg"],
    "Lloyds Banking Group":        ["lloydsbankinggroup", "lbg", "lloyds"],
    "Zurich Insurance":            ["zurich", "zurichinsurance"],
    "Lowe's":                      ["lowes"],
    "Moody's":                     ["moodys", "mco"],
    "NVIDIA":                      ["nvidia"],
    "State Street":                ["statestreet", "globallink"],
}


def slugs_for(company: str) -> list[str]:
    """Candidate URL slugs for a company name (aliases first, then derived)."""
    out = list(ALIASES.get(company, []))
    clean = re.sub(r"\(.*?\)", "", company).strip().lower()
    joined = re.sub(r"[^a-z0-9]", "", clean)
    first = re.split(r"[^a-z0-9]+", clean)[0]
    for s in (joined, first):
        if s and s not in out:
            out.append(s)
    return out


def _india_count(locations: list[str]) -> int:
    return sum(1 for loc in locations if any(h in loc.lower() for h in INDIA_HINTS))


# ── Platform probes — each returns dict(entry) on hit, None on miss ───────────

# Known (host, tenant, site) candidates for big tenants — VERIFIED by a live
# POST before being accepted, so a wrong guess here just falls through to
# generic discovery; it can't produce a false registry entry.
WORKDAY_KNOWN: dict[str, tuple[str, str, str]] = {
    "Commonwealth Bank (CBA)": ("cba.wd3.myworkdayjobs.com", "cba", "CommBank_Careers"),
    "Mastercard":      ("mastercard.wd1.myworkdayjobs.com", "mastercard", "CorporateCareers"),
    "NVIDIA":          ("nvidia.wd5.myworkdayjobs.com", "nvidia", "NVIDIAExternalCareerSite"),
    "Adobe":           ("adobe.wd5.myworkdayjobs.com", "adobe", "external_experienced"),
    "S&P Global":      ("spgi.wd5.myworkdayjobs.com", "spgi", "SPGI_Careers"),
    "Target":          ("target.wd5.myworkdayjobs.com", "target", "targetcareers"),
    "Salesforce":      ("salesforce.wd12.myworkdayjobs.com", "salesforce", "External_Career_Site"),
    "Thomson Reuters": ("thomsonreuters.wd5.myworkdayjobs.com", "thomsonreuters", "External_Career_Site"),
    "State Street":    ("statestreet.wd1.myworkdayjobs.com", "statestreet", "Global"),
    "BlackRock":       ("blackrock.wd1.myworkdayjobs.com", "blackrock", "BlackRock_Professional"),
    "Walmart Global Tech": ("walmart.wd5.myworkdayjobs.com", "walmart", "WalmartExternal"),
    "LSEG (London Stock Exchange Group)": ("lseg.wd3.myworkdayjobs.com", "lseg", "careers"),
}

_WD_SHARDS = ("wd1", "wd3", "wd5", "wd12", "wd2", "wd10")


def _wd_site_candidates(slug: str) -> list[str]:
    cap = slug.capitalize()
    return ["External", "Careers", "External_Careers", "External_Career_Site",
            "ExternalCareerSite", "Global", "careers", "Search",
            f"{cap}_Careers", f"{cap}Careers", f"{slug}careers", f"{slug}_careers"]


def _wd_try(host: str, tenant: str, site: str) -> int | None:
    """POST the cxs jobs API. Returns India job count on 200, None otherwise."""
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {"locationCountry": [INDIA_FACET]},
            "limit": 1, "offset": 0, "searchText": ""}
    r = requests.post(api, json=body,
                      headers={**UA, "Content-Type": "application/json"},
                      timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    return r.json().get("total", 0)


def probe_workday(company: str, slugs: list[str]) -> dict | None:
    # 1) Known tenant/site guess — verified live.
    if company in WORKDAY_KNOWN:
        host, tenant, site = WORKDAY_KNOWN[company]
        try:
            total = _wd_try(host, tenant, site)
            if total is not None:
                return {"platform": "workday", "host": host, "tenant": tenant,
                        "site": site, "india_jobs": total}
        except Exception:
            pass

    # 2) Generic discovery. Trick: POST with a junk site name —
    #    404 means the tenant EXISTS on this shard (wrong site),
    #    422 means the tenant does not exist. Verified June 2026.
    for slug in slugs:
        for wd in _WD_SHARDS:
            host = f"{slug}.{wd}.myworkdayjobs.com"
            try:
                probe = requests.post(
                    f"https://{host}/wday/cxs/{slug}/zzprobe/jobs",
                    json={"limit": 1, "offset": 0},
                    headers={**UA, "Content-Type": "application/json"},
                    timeout=TIMEOUT)
                if probe.status_code != 404:
                    continue  # 422 = no such tenant on this shard
                for site in _wd_site_candidates(slug):
                    try:
                        total = _wd_try(host, slug, site)
                        if total is not None:
                            return {"platform": "workday", "host": host,
                                    "tenant": slug, "site": site,
                                    "india_jobs": total}
                    except Exception:
                        continue
                break  # tenant found but no site candidate matched — stop shards
            except Exception:
                continue
    return None


def probe_greenhouse(company: str, slugs: list[str]) -> dict | None:
    for slug in slugs:
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                             headers=UA, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            jobs = r.json().get("jobs", [])
            if not jobs:
                continue
            india = _india_count([(j.get("location") or {}).get("name", "") for j in jobs])
            return {"platform": "greenhouse", "board_token": slug,
                    "total_jobs": len(jobs), "india_jobs": india}
        except Exception:
            continue
    return None


def probe_lever(company: str, slugs: list[str]) -> dict | None:
    for slug in slugs:
        try:
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json",
                             headers=UA, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            jobs = r.json()
            if not isinstance(jobs, list) or not jobs:
                continue
            india = _india_count([(j.get("categories") or {}).get("location", "") or ""
                                  for j in jobs])
            return {"platform": "lever", "site": slug,
                    "total_jobs": len(jobs), "india_jobs": india}
        except Exception:
            continue
    return None


def probe_smartrecruiters(company: str, slugs: list[str]) -> dict | None:
    for slug in slugs:
        try:
            r = requests.get(
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?country=in&limit=100",
                headers=UA, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            data = r.json()
            total = data.get("totalFound", 0)
            if total == 0 and not data.get("content"):
                # Company exists check: totalFound 0 with valid response still counts
                # as a hit only if the company slug resolves at all.
                r2 = requests.get(
                    f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
                    headers=UA, timeout=TIMEOUT)
                if r2.status_code != 200 or r2.json().get("totalFound", 0) == 0:
                    continue
            return {"platform": "smartrecruiters", "company_id": slug,
                    "india_jobs": total}
        except Exception:
            continue
    return None


def probe_oracle(company: str, slugs: list[str]) -> dict | None:
    for slug in slugs:
        for site in ("CX_1001", "CX_1", "CX_2"):
            try:
                url = (f"https://{slug}.fa.oraclecloud.com/hcmRestApi/resources/latest/"
                       f"recruitingCEJobRequisitions?onlyData=true&"
                       f"finder=findReqs;siteNumber={site},keyword=%22India%22,limit=10")
                r = requests.get(url, headers=UA, timeout=TIMEOUT)
                if r.status_code != 200:
                    continue
                items = r.json().get("items", [])
                if not items:
                    continue
                total = items[0].get("TotalJobsCount", 0)
                if not total:
                    continue
                return {"platform": "oracle_orc", "host": f"{slug}.fa.oraclecloud.com",
                        "site_number": site, "india_jobs": total}
            except Exception:
                continue
    return None


def probe_eightfold(company: str, slugs: list[str]) -> dict | None:
    candidates = []
    for slug in slugs:
        candidates.append((f"careers.{slug}.com", f"{slug}.com"))
        candidates.append((f"{slug}.eightfold.ai", f"{slug}.com"))
    for host, domain in candidates:
        try:
            url = (f"https://{host}/api/apply/v2/jobs?"
                   f"domain={domain}&location=India&num=10")
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            if r.status_code != 200 or "json" not in r.headers.get("Content-Type", ""):
                continue
            data = r.json()
            count = data.get("count", 0)
            if not data.get("positions") and not count:
                continue
            return {"platform": "eightfold", "host": host, "domain": domain,
                    "india_jobs": count}
        except Exception:
            continue
    return None


PROBES = [probe_workday, probe_oracle, probe_eightfold,
          probe_smartrecruiters, probe_greenhouse, probe_lever]


def probe_company(company: str) -> tuple[str, dict | None]:
    slugs = slugs_for(company)
    for probe in PROBES:
        hit = probe(company, slugs)
        if hit:
            return company, hit
    return company, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="IT & Data Engineering")
    ap.add_argument("--company", default="", help="probe a single company instead")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if args.company:
        companies = [args.company]
    else:
        companies = domain_catalog.companies_for_domain(args.domain)

    print(f"Probing {len(companies)} companies (workers={args.workers}) — "
          f"this takes a few minutes…\n")

    results: dict[str, dict | None] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(probe_company, c): c for c in companies}
        for fut in as_completed(futures):
            company, hit = fut.result()
            results[company] = hit
            if hit:
                print(f"  ✓ {company:<42} {hit['platform']:<16} "
                      f"india_jobs={hit.get('india_jobs', '?')}")
            else:
                print(f"  ✗ {company:<42} no public ATS endpoint found")

    hits = {c: h for c, h in results.items() if h}
    print(f"\n=== {len(hits)}/{len(companies)} companies have a direct connector ===")
    by_platform: dict[str, list[str]] = {}
    for c, h in hits.items():
        by_platform.setdefault(h["platform"], []).append(c)
    for p, cos in sorted(by_platform.items()):
        print(f"  {p}: {', '.join(sorted(cos))}")

    out = Path(__file__).parent / "probe_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
