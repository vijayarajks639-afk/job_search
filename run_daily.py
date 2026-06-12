"""
Orchestrator: fetch seed jobs -> agentic search/match -> report -> email.
Invoked by Windows Task Scheduler at 06:00 and 22:00 IST.

Usage:
    python run_daily.py                # full run + email
    python run_daily.py --no-email     # build report, skip sending
    python run_daily.py --no-fetch     # reuse latest seed file, skip seed fetch
    python run_daily.py --model sonnet
    python run_daily.py --companies "JPMorgan Chase,Goldman Sachs"
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

import config
from sources.companies import split_by_coverage


def _filter_to_selected(matches: list[dict], companies_arg: str) -> list[dict]:
    """
    When a company-specific search is triggered from the dashboard, drop any
    carry-forward matches that belong to other companies so they don't pollute
    the results (e.g. ANZ from yesterday bleeding into a JPMorgan search).
    """
    if not companies_arg:
        return matches  # full run — keep everything
    selected_lower = [c.strip().lower() for c in companies_arg.split(",") if c.strip()]
    out = []
    for m in matches:
        co = (m.get("company") or "").lower()
        # Accept if any selected name is contained in the company field or vice-versa.
        if any(sel in co or co in sel for sel in selected_lower):
            out.append(m)
    return out


def _record_history(companies_arg: str, fresh_n: int, matches: list[dict],
                    meta: dict) -> None:
    """
    Append this run to data/search_history.json (newest first, capped at 10).
    The dashboard shows the last 3 so the user has context when they return.
    """
    hist_file = config.DATA_DIR / "search_history.json"
    try:
        history = json.loads(hist_file.read_text(encoding="utf-8")) if hist_file.exists() else []
    except Exception:
        history = []
    history.insert(0, {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "companies": [c.strip() for c in companies_arg.split(",") if c.strip()],
        "fresh": fresh_n,
        "shown": len(matches),
        "web_searches": meta.get("web_searches"),
        "cost_usd": meta.get("cost_usd"),
        "top_matches": [
            {"company": m.get("company"), "title": m.get("title"),
             "fit_score": m.get("fit_score"), "url": m.get("url")}
            for m in matches[:5]
        ],
    })
    hist_file.write_text(json.dumps(history[:10], indent=2, ensure_ascii=False),
                         encoding="utf-8")


def _log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with (config.LOGS_DIR / "run_daily.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email",  action="store_true")
    ap.add_argument("--no-fetch",  action="store_true")
    ap.add_argument("--model",     default="sonnet")
    ap.add_argument("--companies", default="",
                    help="comma-separated company names from the dashboard")
    args = ap.parse_args()

    config.ensure_dirs()
    scope = f"companies={args.companies}" if args.companies else "all GCCs"
    _log(f"=== run_daily start (model={args.model}, email={not args.no_email}, scope={scope}) ===")

    # Persist the search scope so the dashboard can default its Matches view
    # to only the companies of the most recent search.
    (config.DATA_DIR / "last_scope.json").write_text(json.dumps({
        "companies": [c.strip() for c in args.companies.split(",") if c.strip()],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False), encoding="utf-8")

    try:
        # 0) Coverage split: which selected companies have a direct connector,
        #    which fall to the Adzuna aggregator, which need agent web search.
        selected = [c.strip() for c in args.companies.split(",") if c.strip()]
        if selected:
            connector_cos, uncovered = split_by_coverage(selected)
            aggregator_cos = uncovered if config.AGGREGATOR_ENABLED else []
            websearch_cos  = [] if config.AGGREGATOR_ENABLED else uncovered
        else:
            connector_cos, aggregator_cos, websearch_cos = [], [], []  # full run
        _log(f"coverage: connector={connector_cos or 'all registered'} | "
             f"aggregator={aggregator_cos or '—'} | "
             f"web-search={websearch_cos or ('full GCC sweep' if not selected else '—')}")

        # 1) Seed fetch — direct connectors + aggregator fallback
        if args.no_fetch:
            _log("seeds: skipped (--no-fetch)")
        else:
            import fetch_jobs
            raw, status = fetch_jobs.fetch_all(companies_filter=args.companies)
            agg_raw, agg_status = fetch_jobs.fetch_aggregator(aggregator_cos)
            raw.extend(agg_raw)
            status.update(agg_status)
            # Aggregator companies that yielded nothing fall through to web search.
            if aggregator_cos:
                got = {p.company for p in agg_raw}
                websearch_cos.extend(c for c in aggregator_cos if c not in got)
            filtered = fetch_jobs.apply_filters(raw)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            (config.JOBS_RAW_DIR / f"seeds_{ts}.json").write_text(
                json.dumps({"generated_at": datetime.now().isoformat(),
                            "source_status": status, "count": len(filtered),
                            "postings": [p.to_dict() for p in filtered]},
                           indent=2, ensure_ascii=False), encoding="utf-8")
            _log(f"seeds: {status or 'none matched'}; {len(filtered)} recent after filters")

        # 2) Agentic search + match + honest tailoring.
        #    The agent only web-searches companies that have no seed data —
        #    connector/aggregator companies already have exact, dated postings.
        import agent_run
        import carry
        payload = agent_run.run_agent(
            args.model,
            companies=",".join(websearch_cos),
            scoped=bool(selected),
        )
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        matched_path = config.JOBS_MATCHED_DIR / f"matched_{ts}.json"
        matched_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                encoding="utf-8")
        meta    = payload.get("_meta", {})
        fresh_n = len(payload.get("matches", []))

        # Carry-forward — merge with rolling 7-day store, then scope to selected
        # companies so that a JPMorgan search doesn't surface yesterday's ANZ roles.
        payload  = carry.merge(payload)
        payload["matches"] = _filter_to_selected(
            payload.get("matches", []), args.companies
        )
        matches = payload.get("matches", [])
        c = payload.get("_carry", {})
        _log(f"agent: {fresh_n} fresh, {meta.get('web_searches')} searches, "
             f"~${meta.get('cost_usd')}; report shows {len(matches)} "
             f"({c.get('carried_from_prior')} carried)")
        _record_history(args.companies, fresh_n, matches, meta)

        # 3) Report (HTML + PDF)
        from report import generate_report as R
        html_body = R.build_html(payload)
        pdf_path  = config.REPORT_DIR / f"report_{ts}.pdf"
        R.build_pdf(payload, pdf_path)
        (config.REPORT_DIR / f"report_{ts}.html").write_text(html_body, encoding="utf-8")
        _log(f"report: {pdf_path.name}")

        # 4) Email
        if args.no_email:
            _log("email: skipped (--no-email)")
        else:
            import send_report
            service = send_report.get_gmail_service()
            subject = (
                config.REPORT_SUBJECT.format(
                    date=datetime.now().strftime("%d %b %Y"),
                    slot=send_report._slot(),
                ) + f" — {len(matches)} roles"
            )
            mid = send_report._send(service, subject, html_body, str(pdf_path))
            _log(f"email: sent to {config.REPORT_RECIPIENT} (id {mid})")

        _log("=== run_daily done ===")
        return 0

    except Exception as e:
        _log(f"ERROR: {type(e).__name__}: {e}")
        _log(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
