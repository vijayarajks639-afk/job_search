"""
Email the job-search report (HTML body + PDF attachment) to the configured
recipient via the Gmail API.

SAFETY: this only ever sends to config.REPORT_RECIPIENT (the user's own address:
vijayaraj.ks639@gmail.com). It never messages contacts or anyone else, and uses
no CC/BCC.

Usage:
    python send_report.py --matched data/jobs_matched/matched_X.json
    python send_report.py            # uses the latest matched file
    python send_report.py --test     # sends a tiny test email to verify delivery
"""

from __future__ import annotations

import argparse
import base64
import glob
import json
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

sys.stdout.reconfigure(encoding="utf-8")

import config
from auth import get_gmail_service
from report import generate_report as R


def _latest_matched():
    files = sorted(glob.glob(str(config.JOBS_MATCHED_DIR / "matched_*.json")))
    return files[-1] if files else None


def _slot() -> str:
    return "Morning" if datetime.now().hour < 14 else "Evening"


def _send(service, subject: str, html_body: str, pdf_path: str | None) -> str:
    # Single, hard-coded recipient — the user's own address. No CC/BCC.
    msg = MIMEMultipart("mixed")
    msg["To"] = config.REPORT_RECIPIENT
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("Your job-search report is attached / view in HTML.", "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    if pdf_path:
        with open(pdf_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment",
                        filename=f"job_search_report_{datetime.now():%Y%m%d}.pdf")
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent.get("id", "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matched", help="path to a matched_*.json (default: latest)")
    ap.add_argument("--test", action="store_true", help="send a minimal test email")
    args = ap.parse_args()

    service = get_gmail_service()

    if args.test:
        body = ("<p>Test email from the job-search reporter. "
                "If you can read this, Gmail delivery works.</p>")
        mid = _send(service, "Job Search Reporter — test email", body, None)
        print(f"Test email sent to {config.REPORT_RECIPIENT} (id {mid}).")
        return

    path = args.matched or _latest_matched()
    if not path:
        print("No matched_*.json found — run agent_run.py first.")
        return
    payload = json.loads(open(path, encoding="utf-8").read())

    html_body = R.build_html(payload)
    pdf_path = config.REPORT_DIR / f"report_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    R.build_pdf(payload, pdf_path)

    n = len(payload.get("matches", []))
    subject = config.REPORT_SUBJECT.format(date=datetime.now().strftime("%d %b %Y"),
                                           slot=_slot()) + f" — {n} roles"
    mid = _send(service, subject, html_body, str(pdf_path))
    print(f"Report ({n} roles) sent to {config.REPORT_RECIPIENT} (id {mid}).")


if __name__ == "__main__":
    main()
