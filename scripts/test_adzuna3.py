"""Check alternate company names for companies returning 0 from Adzuna."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import requests
import config

BASE = "https://api.adzuna.com/v1/api/jobs/in/search/1"
AUTH = {"app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY}

for name in ["ANZ", "Australia New Zealand Banking", "ANZ Bank", "ANZ Banking",
             "UBS", "UBS Group", "UBS AG", "Citibank", "Citigroup", "Citi India",
             "Nomura India", "Macquarie India", "Macquarie Group"]:
    r = requests.get(BASE, params={**AUTH, "what": name, "results_per_page": 5, "max_days_old": 60}, timeout=30)
    if r.status_code != 200:
        print(f"[{r.status_code}] {name}")
        continue
    d = r.json()
    n_lower = name.lower()
    hits = [
        j for j in d.get("results", [])
        if n_lower in (j.get("company") or {}).get("display_name", "").lower()
        or (j.get("company") or {}).get("display_name", "").lower() in n_lower
    ]
    all_cos = list({(j.get("company") or {}).get("display_name", "") for j in d.get("results", [])})[:5]
    print(f"{name}: {len(hits)} hits | top companies in results: {all_cos}")
