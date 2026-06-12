"""Probe different Adzuna parameter combinations to find what India endpoint accepts."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import requests
import config

BASE = "https://api.adzuna.com/v1/api/jobs/in/search/1"
AUTH = {"app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY}

tests = [
    ("what=Goldman Sachs data",          {**AUTH, "what": "Goldman Sachs data", "results_per_page": 5}),
    ("company=Goldman Sachs",            {**AUTH, "company": "Goldman Sachs", "results_per_page": 5}),
    ("company=Goldman Sachs+max_days",   {**AUTH, "company": "Goldman Sachs", "max_days_old": 30, "results_per_page": 5}),
    ("company=Bank of America+max_days", {**AUTH, "company": "Bank of America", "max_days_old": 30, "results_per_page": 5}),
    ("no filter - just auth",            {**AUTH, "results_per_page": 3}),
    ("what=data engineering India",      {**AUTH, "what": "data engineering", "where": "India", "results_per_page": 5}),
]

for label, params in tests:
    r = requests.get(BASE, params=params, timeout=30)
    if r.status_code == 200:
        d = r.json()
        print(f"[{r.status_code}] {label}: count={d.get('count')} results={len(d.get('results', []))}")
        for j in d.get("results", [])[:2]:
            co = (j.get("company") or {}).get("display_name", "?")
            print(f"  {co}: {j.get('title')} [{j.get('created','')[:10]}]")
    else:
        print(f"[{r.status_code}] {label}: {r.text[:150]}")
