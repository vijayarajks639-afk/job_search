# Job Search Automation

A local, scheduled pipeline that finds recently opened jobs at target India GCCs,
scores fitment against a real resume using Claude Code (headless), produces honest
ATS-tailored resumes, and emails a twice-daily report.

> Built as a personal tool **and** as an Agentic-AI portfolio piece.

## Pipeline

```
fetch_jobs.py   ->  pull recent (<=7d) postings from careers portals, filter + dedupe
match_jobs.py   ->  `claude -p` scores fitment (3 hats) + drafts honest tailoring/referrals
report/         ->  HTML + PDF report
send_report.py  ->  email report to the configured recipient via Gmail API
run_daily.py    ->  orchestrates the above; run by Windows Task Scheduler at 06:00 & 22:00 IST
```

## Setup

```powershell
pip install -r requirements.txt
# Reuse the OAuth client from the gmail_cleanup project:
copy ..\data_engg\gmail_cleanup\credentials.json .\credentials.json
python auth.py            # one-time browser consent; adds gmail.send scope
```

## Honesty & safety guardrails

- Tailored resumes are generated **only** from `resume/master_resume.md` (real history).
- Genuine skill gaps are routed to a "Continuous Learning (In Progress)" section — never
  presented as production experience.
- Job sources are best-effort: the report states which portals actually returned data.
- **No outreach is ever sent.** Referral suggestions are DRAFTS surfaced in the report for
  your own reference only — the pipeline never messages or emails your contacts. The only
  email it sends is the report, to your own address (`REPORT_RECIPIENT` in config.py).
- The headless agent runs with web search only (`--allowedTools WebSearch WebFetch`); it
  has no ability to send mail or message anyone.

## Optional inputs (gitignored — PII)

- `profile/linkedin_profile.pdf` — LinkedIn "Save to PDF" export; enriches the master resume.
- `profile/contacts.csv` — referral contacts at target companies (see `contacts.example.csv`
  for the format). Used to draft warm-intro messages.

## Commands

| Command | Purpose |
|---|---|
| `python fetch_jobs.py --dry-run` | Per-source posting counts, no files written |
| `python run_daily.py --no-email` | Full run, report saved locally, no email sent |
| `python send_report.py --test` | Send a test email to verify Gmail delivery |
| `python run_daily.py` | Full run + email |
| `scheduler\setup_tasks.ps1` | Register the 06:00 & 22:00 IST scheduled tasks (run once) |

## Not included (by design)

- Naukri / LinkedIn scraping — both block automation and restrict it in their ToS.
  LinkedIn is supported only as a manual profile export.
