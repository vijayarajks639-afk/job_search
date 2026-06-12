"""
Streamlit Job Search Dashboard.

Features:
- Tab 1 "Matches": view carry-forward match cards with live filtering + run progress banner
- Tab 2 "New Search": resume upload, company tier picker, trigger agentic scan
- Live progress polling (auto-refreshes every 3 s while a run is active)

Launch:  python -m streamlit run dashboard.py
Or:      scheduler/run_dashboard.bat
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import domain_catalog
import agent_run as _agent_run

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Search Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# domain_catalog and agent_run imported below after sys.path insert

# ── Visual constants ──────────────────────────────────────────────────────────
SCORE_GREEN = "#2e7d32"
SCORE_AMBER = "#e65100"
SCORE_GREY  = "#757575"
VERDICT_COLOR = {"shortlist": "#2e7d32", "maybe": "#e65100", "pass": "#c62828"}
HAT_LABELS = {
    "hr_director":    "HR Director",
    "hiring_manager": "Hiring Manager",
    "recruiter":      "Recruiter",
}

STORE = config.DATA_DIR / "seen_matches.json"
LOG   = config.LOGS_DIR / "run_daily.log"


# ── Data helpers ──────────────────────────────────────────────────────────────
def load_matches() -> list[dict]:
    if not STORE.exists():
        return []
    raw = json.loads(STORE.read_text(encoding="utf-8"))
    return sorted(raw.values(), key=lambda x: x.get("fit_score") or 0, reverse=True)


def load_search_history(limit: int = 3) -> list[dict]:
    """Last N search runs (written by run_daily.py)."""
    hist_file = config.DATA_DIR / "search_history.json"
    if not hist_file.exists():
        return []
    try:
        return json.loads(hist_file.read_text(encoding="utf-8"))[:limit]
    except Exception:
        return []


def load_last_scope() -> dict:
    """Companies of the most recent search (written by run_daily.py)."""
    scope_file = config.DATA_DIR / "last_scope.json"
    if not scope_file.exists():
        return {}
    try:
        return json.loads(scope_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _company_in_scope(company: str, scope_companies: list[str]) -> bool:
    """Substring match both ways — handles 'ANZ' vs 'ANZ Banking Group' etc."""
    co = company.lower()
    return any(sel.lower() in co or co in sel.lower() for sel in scope_companies)


def _log_lines() -> list[str]:
    if not LOG.exists():
        return []
    return LOG.read_text(encoding="utf-8", errors="replace").splitlines()


def load_run_status() -> dict:
    lines = _log_lines()
    start_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if "run_daily start" in lines[i]:
            start_idx = i
            break
    if start_idx is None:
        return {}
    status: dict = {}
    for line in lines[start_idx:]:
        s = line.strip()
        if "run_daily start" in s:
            try:
                status["run_time"] = s[1:20]
            except Exception:
                pass
        elif "seeds:" in s:
            status["seeds_line"] = s.split("] ", 1)[-1]
        elif "agent:" in s:
            status["agent_line"] = s.split("] ", 1)[-1]
        elif "email: sent" in s:
            status["email_sent"] = True
        elif "run_daily done" in s:
            status["done"] = True
        elif "ERROR:" in s:
            status["error"] = s.split("] ", 1)[-1]
    return status


# ── Progress tracking helpers ─────────────────────────────────────────────────
def _current_log_line_count() -> int:
    return len(_log_lines())


def _run_finished_since(start_line: int) -> tuple[bool, bool]:
    """Returns (done, error) by scanning log lines after start_line."""
    lines = _log_lines()
    tail = lines[start_line:]
    done  = any("run_daily done" in l for l in tail)
    error = any("ERROR:" in l for l in tail)
    return done, error


def _log_tail_since(start_line: int, max_lines: int = 12) -> str:
    lines = _log_lines()
    tail = lines[start_line:] or lines[-max_lines:]
    return "\n".join(tail[-max_lines:])


# ── Badge helpers ─────────────────────────────────────────────────────────────
def score_badge_html(score: int) -> str:
    color = SCORE_GREEN if score >= 70 else (SCORE_AMBER if score >= 55 else SCORE_GREY)
    return (f'<span style="background:{color};color:white;padding:3px 12px;'
            f'border-radius:14px;font-weight:bold;font-size:1.05em;">FIT {score}</span>')


def verdict_badge_html(verdict: str) -> str:
    color = VERDICT_COLOR.get((verdict or "").lower(), SCORE_GREY)
    return (f'<span style="background:{color};color:white;padding:2px 9px;'
            f'border-radius:8px;font-size:0.83em;font-weight:bold;">'
            f'{(verdict or "—").upper()}</span>')


# Direct ATS connectors — live company career-site APIs with exact dates.
_LIVE_API_SOURCES = {
    "workday": "Workday", "darwinbox": "Darwinbox", "eightfold": "Eightfold",
    "oracle": "Oracle", "smartrecruiters": "SmartRecruiters",
    "greenhouse": "Greenhouse", "lever": "Lever",
}


def source_badge_html(source: str) -> str:
    src = (source or "").lower()
    for key, label in _LIVE_API_SOURCES.items():
        if key in src:
            return ('<span style="background:#1565c0;color:white;padding:2px 9px;'
                    f'border-radius:6px;font-size:0.78em;">✓ {label} — live API</span>')
    if "adzuna" in src:
        return ('<span style="background:#6a1b9a;color:white;padding:2px 9px;'
                'border-radius:6px;font-size:0.78em;">Adzuna aggregator — dated, verify on site</span>')
    return ('<span style="background:#e65100;color:white;padding:2px 9px;'
            'border-radius:6px;font-size:0.78em;">⚠ Web search — verify link before applying</span>')


# ── Resume upload helpers ─────────────────────────────────────────────────────
def _extract_pdf_text(data: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()
    except ImportError:
        return ""


def _save_resume(uploaded_file) -> tuple[bool, str]:
    """
    Saves uploaded file to master_resume.md (MD/TXT) or extracts text from PDF.
    Returns (success, message).
    """
    name = uploaded_file.name.lower()
    data = uploaded_file.read()

    if name.endswith((".md", ".txt")):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        config.MASTER_RESUME.write_text(text, encoding="utf-8")
        return True, f"Resume saved from `{uploaded_file.name}` ({len(text):,} chars)."

    if name.endswith(".pdf"):
        text = _extract_pdf_text(data)
        if not text:
            return False, (
                "`pypdf` is not installed or PDF has no extractable text. "
                "Install it (`pip install pypdf`) or upload a `.md` / `.txt` version."
            )
        config.MASTER_RESUME.write_text(text, encoding="utf-8")
        return True, (
            f"PDF text extracted and saved as `master_resume.md` "
            f"({len(text):,} chars). Review for any formatting issues before running a search."
        )

    return False, "Unsupported file type. Upload `.md`, `.txt`, or `.pdf`."


# ── Agent run loader ─────────────────────────────────────────────────────────
def load_last_agent_run() -> dict:
    files = sorted(config.JOBS_MATCHED_DIR.glob("matched_*.json"))
    if not files:
        return {}
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_stale(m: dict, today: str) -> bool:
    """True when a web-search role has no confirmed date and is >3 days old in the store."""
    if m.get("posted_date"):
        return False
    first_s = m.get("first_seen", "")
    if not first_s:
        return False
    try:
        from datetime import date as _date
        age = (_date.fromisoformat(today) - _date.fromisoformat(first_s)).days
        return age > 3
    except Exception:
        return False


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar() -> None:
    st.sidebar.title("Job Search")
    if st.sidebar.button("↺  Refresh data", use_container_width=True):
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Pipeline Status")
    status = load_run_status()
    if status:
        if "run_time" in status:
            st.sidebar.markdown(f"**Last run:** `{status['run_time']}`")
        if "seeds_line" in status:
            st.sidebar.caption(status["seeds_line"])
        if "agent_line" in status:
            st.sidebar.caption(status["agent_line"])
        if status.get("error"):
            st.sidebar.error(status["error"])
        elif status.get("done"):
            st.sidebar.success("Last run completed")
        else:
            st.sidebar.warning("Run in progress…")
    else:
        st.sidebar.caption("No run log yet")

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Scheduled: 06:00 & 22:00 IST  \n"
        "Re-register: `scheduler/setup_tasks.ps1`"
    )


# ── Run-in-progress banner ────────────────────────────────────────────────────
_EST_TOTAL_SEC = 180  # ~3 minutes typical run time

def _fmt_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def render_progress_banner() -> None:
    """
    Shown above the tabs whenever a run is active.
    - Polls every 3 s via time.sleep + st.rerun()
    - Shows elapsed time (actual) and estimated remaining
    """
    start_line: int = st.session_state.get("run_start_line", 0)
    done, error = _run_finished_since(start_line)

    if done or error:
        st.session_state.pop("run_triggered", None)
        st.session_state.pop("run_start_line", None)
        st.session_state.pop("run_start_ts", None)
        if error:
            st.error("Search run encountered an error. See log details in the sidebar.")
        else:
            st.success(
                "Search complete — matches updated. "
                "Switch to the **Matches** tab to review results."
            )
        return

    # Compute elapsed time
    start_ts_str: str = st.session_state.get("run_start_ts", "")
    elapsed_sec: float = 0.0
    if start_ts_str:
        try:
            started = datetime.fromisoformat(start_ts_str)
            elapsed_sec = (datetime.now() - started).total_seconds()
        except Exception:
            pass

    remaining_sec = max(0, _EST_TOTAL_SEC - elapsed_sec)
    elapsed_str   = _fmt_elapsed(elapsed_sec)
    remaining_str = _fmt_elapsed(remaining_sec) if remaining_sec > 0 else "finishing up…"

    # Progress label changes per minute
    elapsed_min = int(elapsed_sec // 60)
    step_labels = {
        0: "Reading your resume and identifying target role titles…",
        1: "Searching selected companies for open roles…",
        2: "Scoring fitment against your profile (three-hat review)…",
        3: "Finalising matches and honest tailoring notes…",
    }
    step_msg = step_labels.get(elapsed_min, "Wrapping up — almost done…")

    log_tail = _log_tail_since(start_line)

    with st.status(
        f"Search in progress  |  ⏱ {elapsed_str} elapsed  |  ~{remaining_str} remaining",
        state="running",
        expanded=True,
    ):
        st.markdown(f"**{step_msg}**")
        st.caption(
            "The agent reads your resume → identifies the best-fit role titles → "
            "searches each selected company → scores and tailors results honestly."
        )
        if log_tail:
            st.code(log_tail, language=None)
        else:
            st.caption("Waiting for first log output…")
        st.progress(min(elapsed_sec / _EST_TOTAL_SEC, 0.95))

    time.sleep(3)
    st.rerun()


# ── Tab 1: Matches viewer ─────────────────────────────────────────────────────
def render_matches_tab() -> None:
    all_matches = load_matches()

    if not all_matches:
        st.info(
            "No matches yet. Use the **New Search** tab to trigger a scan, "
            "or wait for the scheduled run at 06:00 / 22:00 IST."
        )
        return

    # ── Scope: default to the companies of the most recent search ────────────
    scope = load_last_scope()
    scope_companies: list[str] = scope.get("companies", [])
    if scope_companies:
        n = len(scope_companies)
        scope_choice = st.radio(
            "Showing",
            [f"Last search only ({n} {'company' if n == 1 else 'companies'})",
             "All stored matches (7-day)"],
            horizontal=True,
            help="Your last search was scoped to: " + ", ".join(scope_companies),
        )
        if scope_choice.startswith("Last search"):
            all_matches = [m for m in all_matches
                           if _company_in_scope(m.get("company", ""), scope_companies)]
            if not all_matches:
                st.warning(
                    "The last search returned no stored matches for: "
                    + ", ".join(scope_companies)
                    + ". Switch to **All stored matches** to see the full 7-day store."
                )
                return

    today = datetime.today().date().isoformat()
    strong  = sum(1 for m in all_matches if (m.get("fit_score") or 0) >= config.FIT_THRESHOLD)
    fresh   = sum(1 for m in all_matches if m.get("first_seen") == today)
    carried = len(all_matches) - fresh

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Roles", len(all_matches))
    c2.metric(f"Strong Fits (≥{config.FIT_THRESHOLD})", strong)
    c3.metric("Found Today", fresh)
    c4.metric("Carried (7-day)", carried)

    # ── Recent search history (last 3 runs) ───────────────────────────────────
    history = load_search_history(limit=3)
    if history:
        with st.expander("🕘 Recent searches (last 3)", expanded=False):
            for i, h in enumerate(history):
                ts = h.get("timestamp", "").replace("T", " ")
                cos = h.get("companies", [])
                scope_txt = (", ".join(cos[:4]) + (f" +{len(cos)-4} more" if len(cos) > 4 else "")
                             if cos else "all GCCs")
                st.markdown(
                    f"**{ts}** — {scope_txt}  ·  "
                    f"{h.get('fresh', 0)} fresh / {h.get('shown', 0)} shown  ·  "
                    f"{h.get('web_searches', '—')} searches"
                )
                for tm in h.get("top_matches", [])[:3]:
                    url = tm.get("url") or ""
                    title_txt = f"{tm.get('company')} — {tm.get('title')} (fit {tm.get('fit_score')})"
                    st.markdown(f"&nbsp;&nbsp;· [{title_txt}]({url})" if url
                                else f"&nbsp;&nbsp;· {title_txt}")
                if i < len(history) - 1:
                    st.markdown("---")

    # ── Agent search transparency panel ───────────────────────────────────────
    last_run = load_last_agent_run()
    if last_run:
        meta        = last_run.get("_meta", {})
        id_roles    = last_run.get("identified_roles", [])
        notes       = last_run.get("search_notes", "")
        gen_at      = last_run.get("generated_at", "")
        with st.expander("🔍 How the last search was done", expanded=False):
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Web Searches Used", meta.get("web_searches", "—"))
            mc2.metric("Model", meta.get("model", "—").replace("claude-", ""))
            cost = meta.get("cost_usd")
            mc3.metric("Estimated Cost", f"~${cost:.4f}" if cost else "—")
            if id_roles:
                st.markdown("**Roles the agent identified from your resume:**")
                st.markdown("  ·  ".join(f"`{r}`" for r in id_roles))
            if notes:
                st.info(f"**Search notes:** {notes}")
            if gen_at:
                st.caption(f"Run at: {gen_at}")

    st.markdown("---")

    fcol1, fcol2, fcol3 = st.columns([2, 3, 2])
    with fcol1:
        min_score = st.slider("Min Fit Score", 0, 100, config.FIT_THRESHOLD, step=5)
    with fcol2:
        all_cos = sorted({m.get("company", "Unknown") for m in all_matches})
        sel_companies = st.multiselect("Filter by Company", all_cos, default=all_cos)
    with fcol3:
        freshness = st.radio("Show", ["All", "Fresh today", "Carried"], horizontal=True)

    filtered = [
        m for m in all_matches
        if (m.get("fit_score") or 0) >= min_score
        and m.get("company", "Unknown") in sel_companies
        and (
            freshness == "All"
            or (freshness == "Fresh today" and m.get("first_seen") == today)
            or (freshness == "Carried" and m.get("first_seen") != today)
        )
    ]

    if not filtered:
        st.info("No roles match the current filters. Try lowering the min fit score.")
        return

    st.subheader(f"{len(filtered)} role{'s' if len(filtered) != 1 else ''}")
    for m in filtered:
        _render_job_card(m, today)


def _render_job_card(m: dict, today: str) -> None:
    score     = m.get("fit_score") or 0
    company   = m.get("company", "Unknown")
    title     = m.get("title", "Untitled")
    loc       = m.get("location", "—")
    source    = m.get("source", "")
    posted    = m.get("posted_date") or "date unknown (web search)"
    first_s   = m.get("first_seen", "")
    url       = m.get("url", "")
    rationale = m.get("rationale", "")
    # "Found today" = first time OUR SYSTEM saw this role today, NOT necessarily posted today
    disc_badge = "Found today" if first_s == today else f"found {first_s}"

    with st.container(border=True):
        hcol, bcol = st.columns([6, 1])
        with hcol:
            st.markdown(f"### {company} — {title}")
            st.markdown(
                f"{source_badge_html(source)}&nbsp;&nbsp;"
                f'<span style="color:#555;font-size:0.85em;">{loc}  |  Posted: {posted}  |  {disc_badge}</span>',
                unsafe_allow_html=True,
            )
        with bcol:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(score_badge_html(score), unsafe_allow_html=True)

        # Staleness warning: unconfirmed date + discovered >3 days ago
        if _is_stale(m, today):
            st.warning(
                "⚠️ This role was first found over 3 days ago and its posting date is "
                "unconfirmed. It may already be closed — verify on the company's careers "
                "site before spending time on an application.",
                icon=None,
            )

        if rationale:
            st.markdown(f"_{rationale}_")

        row = st.columns(3)
        three_hats = m.get("three_hats") or {}
        if three_hats:
            with row[0]:
                with st.expander("Three-Hat Verdicts"):
                    for hat_key, hat_label in HAT_LABELS.items():
                        hat     = three_hats.get(hat_key) or {}
                        verdict = hat.get("verdict", "—")
                        reason  = hat.get("reason", "")
                        st.markdown(
                            f"**{hat_label}** {verdict_badge_html(verdict)}",
                            unsafe_allow_html=True,
                        )
                        if reason:
                            st.caption(reason)

        emphasize = m.get("emphasize") or []
        gaps      = m.get("gaps") or []
        if emphasize or gaps:
            with row[1]:
                with st.expander("Resume Tailoring"):
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        st.markdown("**Emphasise**")
                        for pt in emphasize:
                            st.markdown(f"- {pt}")
                    with tc2:
                        st.markdown("**Gaps → Learning**")
                        for g in gaps:
                            st.markdown(f"- {g}")

        referral = m.get("referral")
        if referral:
            with row[2]:
                with st.expander("Referral draft (your reference only — do not send)"):
                    contact = referral.get("contact", "")
                    message = referral.get("message", "")
                    if contact:
                        st.markdown(f"**Contact:** {contact}")
                    if message:
                        st.text_area(
                            "Draft", value=message, height=100,
                            key=f"ref_{url or title}_{score}", disabled=True,
                        )

        if url:
            st.markdown(f"[View / Apply →]({url})")


# ── Tab 2: New Search ─────────────────────────────────────────────────────────
def _trigger_search(companies: list[str], with_email: bool = False) -> None:
    """Launch run_daily.py as a background process and set progress state."""
    companies_arg = ",".join(companies)
    py = sys.executable
    flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    cmd = [py, str(config.ROOT / "run_daily.py"), "--companies", companies_arg]
    if not with_email:
        cmd.append("--no-email")
    subprocess.Popen(cmd, creationflags=flags)
    st.session_state["run_triggered"]  = True
    st.session_state["run_start_line"] = _current_log_line_count()
    st.session_state["run_start_ts"]   = datetime.now().isoformat()


def render_search_tab() -> None:

    # ── Section A: Resume ──────────────────────────────────────────────────────
    with st.expander("📄  Resume — view / update", expanded=False):
        resume_exists = config.MASTER_RESUME.exists()
        if resume_exists:
            current = config.MASTER_RESUME.read_text(encoding="utf-8")
            lines   = current.splitlines()
            preview = "\n".join(lines[:12]) + (
                f"\n… ({len(lines)} lines total)" if len(lines) > 12 else ""
            )
            st.code(preview, language="markdown")
            st.caption(
                f"`{config.MASTER_RESUME.relative_to(config.ROOT)}`  |  "
                f"{len(current):,} chars  |  {len(lines)} lines"
            )
        else:
            st.warning("No `resume/master_resume.md` found. Upload one below.")

        st.markdown("**Upload a new resume** (replaces the current one):")
        uploaded = st.file_uploader(
            "Upload resume",
            type=["md", "txt", "pdf"],
            help="Markdown / plain text preferred. PDF supported if `pypdf` installed.",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            if st.button("Save uploaded resume", type="primary"):
                ok, msg = _save_resume(uploaded)
                if ok:
                    # Clear cached domain result — resume changed — and refresh
                    # the page so the new resume preview shows immediately.
                    st.session_state.pop("domain_result", None)
                    st.session_state["resume_saved_msg"] = msg
                    st.rerun()
                else:
                    st.error(msg)
        if st.session_state.pop("resume_saved_msg", None):
            st.success("Resume updated. Re-detect your domain below to refresh the company list.")

    st.markdown("---")

    # ── Section B: Domain detection ───────────────────────────────────────────
    st.markdown(
        "**Step 1 — Detect your domain.** "
        "The AI reads your resume, identifies which industry you belong to, "
        "and selects the top 25 most relevant GCCs / companies to search."
    )

    if not config.MASTER_RESUME.exists():
        st.info("Upload a resume above first.")
        return

    detect_col, clear_col = st.columns([3, 1])
    with detect_col:
        detect_btn = st.button(
            "🔍  Detect My Domain & Shortlist Companies",
            use_container_width=True,
            type="secondary",
        )
    with clear_col:
        if st.button("↺  Re-detect", use_container_width=True,
                     disabled="domain_result" not in st.session_state):
            st.session_state.pop("domain_result", None)
            st.rerun()

    if detect_btn:
        resume_text = config.MASTER_RESUME.read_text(encoding="utf-8")
        with st.spinner("Analysing your resume — usually takes 10–20 seconds…"):
            result = _agent_run.detect_domain(resume_text)
        st.session_state["domain_result"] = result
        st.rerun()

    # ── Show detection result ─────────────────────────────────────────────────
    domain_result: dict = st.session_state.get("domain_result", {})
    if not domain_result:
        return

    domain      = domain_result.get("domain", "—")
    sub_domain  = domain_result.get("sub_domain", "")
    confidence  = domain_result.get("confidence", "—")
    reasoning   = domain_result.get("reasoning", "")
    top_cos     = domain_result.get("top_companies", [])

    conf_color = {"high": SCORE_GREEN, "medium": SCORE_AMBER, "low": SCORE_GREY}.get(
        confidence, SCORE_GREY
    )
    st.markdown(
        f'<div style="border:1px solid #ddd;border-radius:8px;padding:12px;margin-bottom:12px;">'
        f'<b style="font-size:1.1em;">Domain detected:</b> {domain}'
        f'{"  ·  <i>" + sub_domain + "</i>" if sub_domain else ""}  '
        f'<span style="background:{conf_color};color:white;padding:2px 8px;'
        f'border-radius:6px;font-size:0.8em;">{confidence} confidence</span>'
        f'{"<br><span style=\'color:#555;font-size:0.9em;\'>" + reasoning + "</span>" if reasoning else ""}'
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Section C: Top 25 companies (pre-selected, user can adjust) ───────────
    st.markdown(
        f"**Step 2 — Confirm companies to search.**  "
        f"Top {len(top_cos)} companies for **{domain}** are pre-selected. "
        f"Uncheck any you want to skip."
    )

    def _set_all_companies():
        for c in top_cos:
            st.session_state[f"dom_co_{c}"] = st.session_state["dom_select_all"]

    st.checkbox(
        "**Select all / none**",
        value=True,
        key="dom_select_all",
        on_change=_set_all_companies,
    )

    selected: list[str] = []
    cols = st.columns(3)
    for i, company in enumerate(top_cos):
        checked = cols[i % 3].checkbox(company, value=True, key=f"dom_co_{company}")
        if checked:
            selected.append(company)

    # Manual add
    with st.expander("➕  Add more companies manually"):
        all_known = sorted({
            co for d in domain_catalog.DOMAINS.values() for co in d["companies"]
            if co not in top_cos
        })
        extras = st.multiselect("Add companies from the full catalog", all_known)
        selected.extend(extras)

    st.markdown("---")

    # ── Section D: Search ────────────────────────────────────────────────────
    sel_count = len(selected)
    run_label = (
        f"▶  Search {sel_count} {'company' if sel_count == 1 else 'companies'}"
        if sel_count else "Select at least one company above"
    )
    if st.button(run_label, disabled=(sel_count == 0), type="primary", use_container_width=True):
        try:
            _trigger_search(selected)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to launch run: {e}")

    with st.expander("Advanced: run full pipeline + send email report"):
        if st.button("Search + send email report", type="secondary"):
            try:
                _trigger_search(selected, with_email=True)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    render_sidebar()

    st.title("Job Search Dashboard")
    st.caption(
        f"Resume-driven agentic job search  |  {datetime.today().strftime('%d %b %Y')}  |  "
        "AI reads your resume → identifies the right roles → searches top India GCCs"
    )

    # Progress banner is shown above tabs whenever a run is active
    if st.session_state.get("run_triggered"):
        render_progress_banner()

    tab_matches, tab_search = st.tabs(["Matches", "New Search"])
    with tab_matches:
        render_matches_tab()
    with tab_search:
        render_search_tab()


if __name__ == "__main__":
    main()
