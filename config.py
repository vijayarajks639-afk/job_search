"""
Central configuration for the job-search automation pipeline.

Paths are resolved relative to this file so the project is portable.
No secrets live here — credentials.json / token.json are gitignored.
"""

import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent

PROFILE_DIR      = ROOT / "profile"
RESUME_DIR       = ROOT / "resume"
MASTER_RESUME    = RESUME_DIR / "master_resume.md"
TAILORED_DIR     = RESUME_DIR / "tailored"
CONTACTS_CSV     = PROFILE_DIR / "contacts.csv"
LINKEDIN_EXPORT  = PROFILE_DIR / "linkedin_profile.pdf"

PROMPTS_DIR      = ROOT / "prompts"
MATCH_PROMPT     = PROMPTS_DIR / "match_prompt.md"

DATA_DIR         = ROOT / "data"
JOBS_RAW_DIR     = DATA_DIR / "jobs_raw"
JOBS_MATCHED_DIR = DATA_DIR / "jobs_matched"
REPORT_DIR       = DATA_DIR / "reports"
LOGS_DIR         = ROOT / "logs"

# Reuse the OAuth client already created for the gmail_cleanup project.
GMAIL_CREDENTIALS = ROOT / "credentials.json"
GMAIL_TOKEN       = ROOT / "token.json"

# ── Email ────────────────────────────────────────────────────────────────────
REPORT_RECIPIENT = "vijayaraj.ks639@gmail.com"
REPORT_SUBJECT   = "Job Search Report — {date} ({slot})"

# ── Matching ─────────────────────────────────────────────────────────────────
# Jobs scoring at/above this fitment get a tailored resume + referral draft.
FIT_THRESHOLD = 70
# Hard cap on jobs sent to the matcher per run (controls Pro usage + latency).
MAX_JOBS_TO_MATCH = 40

# ── Sourcing ─────────────────────────────────────────────────────────────────
# Only postings opened within this many days are considered "recent".
RECENT_DAYS = 7

# Locations we care about (substring match, case-insensitive).
TARGET_LOCATIONS = ["india", "bengaluru", "bangalore", "hyderabad", "chennai",
                    "pune", "mumbai", "gurgaon", "gurugram", "noida"]

# Role keywords aligned to Vijay's targets. A posting must match at least one.
ROLE_KEYWORDS = [
    "data platform", "data engineering", "engineering manager",
    "engineering lead", "platform engineering", "data architect",
    "solution architect", "technology manager", "delivery manager",
    "head of data", "director", "principal engineer", "ai platform",
    "machine learning platform", "mlops", "data governance",
    "analytics platform", "lakehouse", "data mesh",
]

# HTTP politeness
REQUEST_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JobSearchBot/1.0"

# ── Adzuna aggregator (fallback for companies without a direct connector) ────
# Free key: https://developer.adzuna.com/ — set both env vars to enable.
# Without a key the aggregator step is silently skipped (web search fallback).
#
# Windows note: User-level env vars set via System Properties / setx are not
# visible in processes started before the variable was added (e.g. a running
# Streamlit session). We fall back to reading the Windows Registry directly so
# the dashboard's subprocess.Popen calls work without needing a restart.
def _read_env_or_registry(name: str) -> str:
    val = os.environ.get(name, "")
    if val:
        return val
    try:
        import winreg  # Windows-only stdlib module
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Environment", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return val or ""
    except Exception:
        return ""

ADZUNA_APP_ID  = _read_env_or_registry("ADZUNA_APP_ID")
ADZUNA_APP_KEY = _read_env_or_registry("ADZUNA_APP_KEY")
AGGREGATOR_ENABLED = bool(ADZUNA_APP_ID and ADZUNA_APP_KEY)


def ensure_dirs() -> None:
    """Create all output directories if missing (idempotent)."""
    for d in (PROFILE_DIR, RESUME_DIR, TAILORED_DIR, PROMPTS_DIR,
              DATA_DIR, JOBS_RAW_DIR, JOBS_MATCHED_DIR, REPORT_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
