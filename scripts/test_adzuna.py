"""Smoke-test Adzuna connector against uncovered companies."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sources.adzuna import fetch

companies = [
    "Goldman Sachs", "Barclays", "Morgan Stanley", "Citi", "ANZ",
    "Deutsche Bank", "Mastercard", "State Street", "UBS",
    "Bank of America", "Nomura", "Macquarie", "BNP Paribas",
]
total = 0
for co in companies:
    try:
        results = fetch(co, max_days_old=30, results=20)
        total += len(results)
        print(f"{co}: {len(results)} postings")
        for j in results[:2]:
            print(f"  [{j.posted_date}] {j.title} | {j.location}")
    except Exception as e:
        print(f"{co}: ERROR {e}")
print(f"\nTotal: {total} postings across {len(companies)} companies")
