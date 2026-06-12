"""
Orchestrator: fetch seed jobs -> agentic search/match -> report -> email.
Invoked by Windows Task Scheduler at 06:00 and 22:00 IST.

Usage:
    python run_daily.py                # full run + email
    python run_daily.py --no-email     # build report, skip sending
    python run_daily.py --no-fetch     # reuse latest seed file, skip seed fetch
    python run_daily.py --model sonnet
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

import config


def _log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with (config.LOGS_DIR / "run_daily.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--model", default="sonnet")
    args = ap.parse_args()

    config.ensure_dirs()
    _log(f"=== run_daily start (model={args.model}, email={not args.no_email}) ===")

    try:
        # 1) Seed fetch (deterministic Workday/Darwinbox roles)
        if not args.no_fetch:
            import fetch_jobs
            raw, status = fetch_jobs.fetch_all()
            filtered = fetch_jobs.apply_filters(raw)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            (config.JOBS_RAW_DIR / f"seeds_{ts}.json").write_text(
                json.dumps({"generated_at": datetime.now().isoformat(),
                            "source_status": status, "count": len(filtered),
                            "postings": [p.to_dict() for p in filtered]},
                           indent=2, ensure_ascii=False), encoding="utf-8")
            _log(f"seeds: {status}; {len(filtered)} recent after filters")
        else:
            _log("seeds: skipped (--no-fetch)")

        # 2) Agentic search + match + honest tailoring
        import agent_run
        import carry
        payload = agent_run.run_agent(args.model)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        matched_path = config.JOBS_MATCHED_DIR / f"matched_{ts}.json"
        matched_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                encoding="utf-8")
        meta = payload.get("_meta", {})
        fresh_n = len(payload.get("matches", []))

        # Carry-forward: union with strong matches from the last 7 days so recall
        # variance doesn't produce an empty report when good roles still exist.
        payload = carry.merge(payload)
        matches = payload.get("matches", [])
        c = payload.get("_carry", {})
        _log(f"agent: {fresh_n} fresh, {meta.get('web_searches')} searches, "
             f"~${meta.get('cost_usd')}; report shows {len(matches)} "
             f"({c.get('carried_from_prior')} carried)")

        # 3) Report (HTML + PDF)
        from report import generate_report as R
        html_body = R.build_html(payload)
        pdf_path = config.REPORT_DIR / f"report_{ts}.pdf"
        R.build_pdf(payload, pdf_path)
        (config.REPORT_DIR / f"report_{ts}.html").write_text(html_body, encoding="utf-8")
        _log(f"report: {pdf_path.name}")

        # 4) Email (single recipient = user's own address)
        if args.no_email:
            _log("email: skipped (--no-email)")
        else:
            import send_report
            service = send_report.get_gmail_service()
            subject = config.REPORT_SUBJECT.format(
                date=datetime.now().strftime("%d %b %Y"),
                slot=send_report._slot()) + f" — {len(matches)} roles"
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
