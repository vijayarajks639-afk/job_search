"""
Test the full fetch pipeline: connector + aggregator, for a mix of covered and
uncovered companies. Prints per-company status and sample postings.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
config.ensure_dirs()

import fetch_jobs
from sources.companies import split_by_coverage

companies = ["JPMorgan Chase", "HSBC", "Goldman Sachs", "Citi", "Barclays", "Adobe"]
connector_cos, uncovered = split_by_coverage(companies)
aggregator_cos = uncovered if config.AGGREGATOR_ENABLED else []
websearch_cos  = [] if config.AGGREGATOR_ENABLED else uncovered

print(f"Companies: {companies}")
print(f"  connector  : {connector_cos}")
print(f"  aggregator : {aggregator_cos}")
print(f"  web-search : {websearch_cos}")
print(f"  AGGREGATOR_ENABLED: {config.AGGREGATOR_ENABLED}")
print()

# Direct connectors
raw, status = fetch_jobs.fetch_all(companies_filter=",".join(companies))
print("Direct connector results:")
for name, st in status.items():
    print(f"  {name}: {st}")

# Aggregator
agg_raw, agg_status = fetch_jobs.fetch_aggregator(aggregator_cos)
print("\nAggregator results:")
for name, st in agg_status.items():
    print(f"  {name}: {st}")

# Combine + filter
all_raw = raw + agg_raw
filtered = fetch_jobs.apply_filters(all_raw)
print(f"\nTotal: {len(all_raw)} raw -> {len(filtered)} after filters")

from collections import Counter
by_co = Counter(p.company for p in filtered)
for co, n in sorted(by_co.items(), key=lambda x: -x[1]):
    print(f"  {co}: {n}")
