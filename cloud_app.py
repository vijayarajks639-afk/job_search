"""
Public demo of the job-search pipeline — Streamlit Community Cloud entry point.

This is the CLOUD app: a sanitized, self-contained demo. It deliberately does
NOT import agent_run / auth / fetch_jobs connectors that need local state, or
touch profile/, resume/, or any local match data. Live search runs against the
Adzuna India API (key via st.secrets), and optional one-posting AI fit-scoring
runs against the Anthropic API (Haiku) — both rate-limited. The full agentic
pipeline (Claude headless multi-job matching, ATS connectors, Gmail reports)
runs locally; the About tab tells that story.

Run locally:  streamlit run cloud_app.py   (needs .streamlit/secrets.toml)
Deploy:       see cloud/README_DEPLOY.md
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

import config
from sources import adzuna
from domain_catalog import DOMAINS
from cloud import usage, admin, domain_detect, ai_score, search_history

GITHUB_URL = "https://github.com/vijayarajks639-afk/job_search"
SAMPLE_FILE = Path(__file__).resolve().parent / "cloud" / "sample_matches.json"

# Max AI analyses per search — set equal to session cap so only the session
# limit matters (2 total per browser session).
AI_POSTINGS_PER_SEARCH = 2

config.ensure_dirs()

st.set_page_config(page_title="Find me a Job",
                   page_icon="💼", layout="wide")

# Count each browser session once.
if not st.session_state.get("_visit_logged"):
    usage.log_event("visit")
    st.session_state["_visit_logged"] = True
    st.session_state["searches_used"] = 0
    st.session_state["ai_used"] = 0
    st.session_state["recent_searches"] = []


def _clean_company(name: str) -> str:
    """'Philips India (Bengaluru)' -> 'Philips India' — parentheticals hurt
    keyword search and never appear in Adzuna display names."""
    return re.sub(r"\s*\([^)]*\)", "", name).strip()


def _sanitize_keywords(raw: str) -> str:
    """Visitor free-text -> safe keyword string (letters/digits/space and a few
    job-title chars), length-capped."""
    cleaned = re.sub(r"[^A-Za-z0-9 +#./-]", " ", raw)
    return " ".join(cleaned.split())[:60]


def _mask_email(email: str) -> str:
    """'vijayaraj.ks639@gmail.com' -> 'vij***@gmail.com'"""
    local, _, domain = email.partition("@")
    masked_local = local[:3] + "***" if len(local) > 3 else local[0] + "***"
    return f"{masked_local}@{domain}"



def _get_location() -> str:
    """Visitor location from IP geolocation (HTTPS, ipapi.co free tier).
    On Streamlit Cloud: X-Forwarded-For / X-Real-IP carries visitor's real IP.
    Locally: self-lookup returns the machine's public IP city."""
    try:
        import json as _json
        import urllib.request as _req
        headers = st.context.headers
        # Pick the first non-local IP from forwarding headers.
        ip = ""
        for hdr in ("X-Forwarded-For", "X-Real-Ip", "Cf-Connecting-Ip"):
            val = headers.get(hdr, "").split(",")[0].strip()
            if val and val not in ("127.0.0.1", "::1", ""):
                ip = val
                break
        # ipapi.co: pass IP for known addresses; omit for self-lookup (local dev).
        url = f"https://ipapi.co/{ip}/json/" if ip else "https://ipapi.co/json/"
        req = _req.Request(url, headers={"User-Agent": "job-search-demo/1.0"})
        with _req.urlopen(req, timeout=4) as r:
            data = _json.loads(r.read())
        city    = data.get("city", "")
        country = data.get("country_name", "")
        parts   = [p for p in (city, country) if p]
        if parts:
            return ", ".join(parts)
    except Exception:
        pass
    return ""


def _extract_identity(text: str) -> tuple[str | None, str | None]:
    """Best-effort (name, email) from resume plain-text. Returns (None, None)
    when not found. Email via regex; name from first plausible name-line in the
    first 10 lines (2–5 words, letters only, no @ or digits)."""
    email_m = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+", text)
    email = email_m.group(0).lower() if email_m else None
    name = None
    for line in text.strip().splitlines()[:10]:
        line = line.strip()
        words = line.split()
        if (2 <= len(words) <= 5
                and re.match(r"^[A-Za-z][A-Za-z .\-']+$", line)
                and 5 <= len(line) <= 50):
            name = line
            break
    return name, email


# ── Fit-score / verdict badges (same thresholds as local dashboard.py) ───────
def _score_badge_html(score: int) -> str:
    color = "#2e7d32" if score >= 70 else "#e65100" if score >= 55 else "#757575"
    return (f'<span style="background:{color};color:white;padding:3px 12px;'
            f'border-radius:14px;font-weight:bold;font-size:1.05em;">FIT {score}</span>')


_VERDICT_COLOR = {"shortlist": "#2e7d32", "maybe": "#e65100", "pass": "#c62828"}


def _verdict_badge_html(verdict: str) -> str:
    v = (verdict or "").lower()
    color = _VERDICT_COLOR.get(v, "#757575")
    # Strip to letters before display — never let model text into raw HTML.
    label = re.sub(r"[^A-Za-z]", "", verdict or "")[:12].upper() or "—"
    return (f'<span style="background:{color};color:white;padding:2px 9px;'
            f'border-radius:8px;font-size:0.83em;font-weight:bold;">{label}</span>')


def _posting_card(p) -> None:
    posted = p.posted_date or "date unknown"
    st.markdown(
        f"**{p.title}**  \n"
        f"{p.company} · {p.location or 'India'} · posted {posted}"
    )
    if p.description:
        st.caption(p.description[:300] + ("…" if len(p.description) > 300 else ""))
    if p.url:
        st.markdown(f"[View / apply on Adzuna →]({p.url})")


def _render_score(result: dict) -> None:
    st.markdown(_score_badge_html(result["fit_score"]), unsafe_allow_html=True)
    if result.get("rationale"):
        st.caption(result["rationale"])
    with st.expander("Three-Hat Verdicts"):
        for hat_key, label in (("hr_director", "HR Director"),
                               ("hiring_manager", "Hiring Manager"),
                               ("recruiter", "Recruiter")):
            h = result["three_hats"].get(hat_key) or {}
            st.markdown(f"**{label}** {_verdict_badge_html(h.get('verdict'))}",
                        unsafe_allow_html=True)
            if h.get("reason"):
                st.caption(h["reason"])
    emphasize = result.get("emphasize") or []
    gaps = result.get("gaps") or []
    if emphasize or gaps:
        with st.expander("Resume Tailoring (emphasise / gaps)"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Emphasise**")
                for pt in emphasize:
                    st.markdown(f"- {pt}")
            with c2:
                st.markdown("**Gaps → Learning**")
                for g in gaps:
                    st.markdown(f"- {g}")


def _analyze_button(p, key: str, idx: int) -> None:
    no_resume = not st.session_state.get("resume_text")
    session_cap = st.session_state.get("ai_used", 0) >= usage.AI_PER_SESSION
    search_cap = st.session_state.get("analyses_this_search", 0) >= AI_POSTINGS_PER_SEARCH
    disabled = no_resume or session_cap or search_cap
    if no_resume:
        help_txt = "Upload a resume above to analyse fit."
    elif search_cap:
        help_txt = "AI analysis limit reached for this session (max 2)."
    elif session_cap:
        help_txt = "AI-analysis limit reached for this session."
    else:
        help_txt = "Score this posting against your uploaded resume (Anthropic Haiku)."

    if st.button("🤖 Analyse my fit", key=f"ai_{idx}", disabled=disabled, help=help_txt):
        # Pre-check the global cap so we never call the API when over budget.
        if usage.ai_quota_remaining() <= 0:
            st.warning("The demo's AI-analysis quota is used up for now — try again later.")
            return
        try:
            with st.spinner("Scoring against your resume…"):
                result = ai_score.score_posting(st.session_state["resume_text"], p)
        except Exception as exc:
            usage.log_event("error", detail=f"ai_score: {str(exc)[:200]}")
            st.warning("AI analysis failed — please try again.")
            return
        usage.consume_ai_quota(1)  # consume only on success
        st.session_state["ai_results"][key] = result
        st.session_state["ai_used"] = st.session_state.get("ai_used", 0) + 1
        st.session_state["analyses_this_search"] = \
            st.session_state.get("analyses_this_search", 0) + 1
        usage.log_event("ai_score", company=p.company, fit=result["fit_score"])
        st.rerun()


def _render_results() -> None:
    """Render persisted search results (survives Analyse-my-fit reruns)."""
    results = st.session_state.get("results")
    if results is None:
        return
    st.subheader(f"{len(results)} postings found")
    if not results:
        st.info("No recent postings matched. Try a wider date range, fewer "
                "keywords, or different companies.")
        return
    ai_results = st.session_state.setdefault("ai_results", {})
    for idx, p in enumerate(results):
        _posting_card(p)
        key = p.url or f"{p.company}|{p.title}"
        if key in ai_results:
            _render_score(ai_results[key])
        elif config.AI_SCORING_ENABLED:
            _analyze_button(p, key, idx)
        st.divider()


# ── Tabs ─────────────────────────────────────────────────────────────────────
# Visitors see only Search. Admin (owner's resume email) gets About + Admin too.
if st.session_state.get("admin_ok"):
    tab_search, tab_about, tab_admin = st.tabs(
        ["🔍 Search jobs", "ℹ️ About this project", "🔐 Admin"])
else:
    tab_search = st.tabs(["🔍 Search jobs"])[0]
    tab_about = None
    tab_admin = None


with tab_search:
    st.title("Find me a Job")
    st.markdown("##### Resume-driven job matching for India GCCs, with live "
                "postings + AI fit scores")
    if st.session_state.get("admin_ok"):
        st.caption(
            "Upload your resume → we detect your industry domain and pre-select "
            "matching India GCCs → search live postings via the Adzuna jobs API → "
            "optionally get an AI fit score (HR / Hiring-Manager / Recruiter verdicts "
            "+ resume tailoring) on a posting."
        )

    if not config.AGGREGATOR_ENABLED:
        st.error("Search is unavailable: Adzuna API keys are not configured.")
    else:
        # ── Step 1: resume-driven domain detection ──────────────────────────
        st.markdown("#### Step 1 — Your resume")
        up = st.file_uploader(
            "Upload resume (PDF or TXT) — processed in memory only, never stored",
            type=["pdf", "txt"])
        if up is not None and st.session_state.get("_detected_for") != up.name:
            try:
                # In-memory only: extract -> detect. Resume text is kept in
                # st.session_state for optional AI scoring this session; it is
                # never written to disk and never logged.
                text = domain_detect.extract_text(up.read(), up.name)
                st.session_state["resume_text"] = text
                # Identify the visitor from their resume (never stored raw).
                name, email = _extract_identity(text)
                if email:
                    uhash = search_history.user_hash(email)
                    st.session_state["user_hash"] = uhash
                    st.session_state["user_name"] = (
                        name or email.split("@")[0].replace(".", " ").title())
                    st.session_state["user_email_masked"] = _mask_email(email)
                    # Fetch location once per session on first resume upload.
                    if "user_location" not in st.session_state:
                        st.session_state["user_location"] = _get_location()
                    # Grant admin access when the owner uploads their own resume.
                    if email == admin.REPORT_RECIPIENT:
                        st.session_state["admin_ok"] = True
                else:
                    st.session_state.pop("user_hash", None)
                    st.session_state["user_name"] = None
                    st.session_state.pop("user_email_masked", None)
                    st.session_state.pop("user_location", None)
                res = domain_detect.detect(text)
                # Keyword pass found NOTHING (e.g. scanned/image PDF) -> let Claude
                # read the full resume, if the API is on and within the AI budget.
                if res["confidence"] == "none" and config.AI_SCORING_ENABLED \
                        and usage.ai_quota_remaining() > 0:
                    try:
                        d = ai_score.detect_domain(text, list(DOMAINS.keys()))
                        if d:
                            usage.consume_ai_quota(1)
                            res = {"domain": d, "confidence": "ai",
                                   "matched_keywords": [],
                                   "companies": DOMAINS[d]["companies"], "scores": {}}
                            usage.log_event("ai_detect", domain=d)
                    except Exception as exc:
                        usage.log_event("error", detail=f"ai_detect: {str(exc)[:200]}")
                st.session_state["detect_result"] = res
                st.session_state["_detected_for"] = up.name
                usage.log_event("detect", domain=res["domain"],
                                confidence=res["confidence"])
            except Exception as exc:
                usage.log_event("error", detail=f"detect: {str(exc)[:200]}")
                st.warning("Could not read that file — pick a domain manually below.")

        det = st.session_state.get("detect_result")
        if det and det["confidence"] == "none":
            # Genuinely no extractable text (scanned/image PDF) — only here do we
            # force a manual pick.
            st.warning(
                "Couldn't read enough text from this file to detect a domain — "
                "a scanned or image-only PDF can cause this. Pick one manually below.")
            det = None
        elif det and det["confidence"] == "ai":
            st.success(f"Detected domain: **{det['domain']}** — Claude read your "
                       "full resume to classify it. Change it below if needed.")
        elif det and det["confidence"] == "low":
            st.info(f"Best guess: **{det['domain']}** — weak keyword signal, so "
                    "please confirm it or pick a different domain below.")
        elif det:
            st.success(
                f"Detected domain: **{det['domain']}** ({det['confidence']} confidence) "
                f"— matched on keywords like "
                f"*{', '.join(det['matched_keywords'][:5]) or '—'}*. "
                "Adjust below if it got it wrong.")

        # ── Search history — shown once we know who the visitor is ──────────
        session_recent = st.session_state.get("recent_searches", [])
        uhash_val = st.session_state.get("user_hash")
        hist_3d = search_history.get_history(uhash_val) if uhash_val else []

        if session_recent or hist_3d:
            first = (st.session_state.get("user_name") or "").split()[0] or "Your"
            with st.expander(f"📋 {first}'s search activity", expanded=False):
                if session_recent:
                    st.markdown("**This session**")
                    for s in reversed(session_recent):
                        cos = ", ".join(_clean_company(c) for c in s["companies"][:3])
                        if len(s["companies"]) > 3:
                            cos += f" +{len(s['companies']) - 3} more"
                        kw = f" · _{s['keywords']}_" if s["keywords"] else ""
                        st.caption(
                            f"{s['time']} · **{s['domain']}** · {cos}{kw} "
                            f"· {s['results']} result(s)")
                if hist_3d:
                    if session_recent:
                        st.divider()
                    st.markdown("**Past 3 days (all sessions)**")
                    rows = []
                    for s in hist_3d:
                        ts = datetime.fromisoformat(s["ts"])
                        cos = ", ".join(s["companies"][:3])
                        if len(s["companies"]) > 3:
                            cos += f" +{len(s['companies']) - 3}"
                        rows.append({
                            "When (UTC)": ts.strftime("%d %b %H:%M"),
                            "Domain": s["domain"],
                            "Companies": cos,
                            "Keywords": s["keywords"] or "—",
                            "Results": s["results"],
                        })
                    st.table(rows)
                elif uhash_val:
                    st.caption("No searches in the past 3 days across sessions.")

        # ── Step 2: companies — résumé-driven, auto-selected ────────────────
        st.markdown("#### Step 2 — Companies to search")
        domain_names = list(DOMAINS.keys())
        companies: list[str] = []
        domain = None
        kw_raw, days = "", 14

        if det:
            # Résumé drives it: domain pre-selected, top 5 auto-selected — the
            # visitor is NOT asked to pick. They can tweak in the expander.
            domain = st.selectbox("Industry domain", domain_names,
                                  index=domain_names.index(det["domain"]))
            top5 = DOMAINS[domain]["companies"][:usage.MAX_COMPANIES_PER_SEARCH]
            with st.expander("Adjust companies (optional)", expanded=False):
                companies = st.multiselect(
                    f"Companies (max {usage.MAX_COMPANIES_PER_SEARCH})",
                    DOMAINS[domain]["companies"], default=top5,
                    max_selections=usage.MAX_COMPANIES_PER_SEARCH,
                    key=f"cos_{domain}")
            # Never silently fall back — user's explicit selection is used as-is.
            # If they cleared all, Search is disabled (disabled=not companies below).
            if companies:
                st.caption("Will search: **"
                           + ", ".join(_clean_company(c) for c in companies) + "**")
            else:
                st.caption("No companies selected — open *Adjust companies* above "
                           "to pick at least one.")
        else:
            st.info("⬆️ Upload your resume above to auto-detect your domain and "
                    "matching companies — or browse manually below.")
            with st.expander("Browse by domain manually", expanded=False):
                domain = st.selectbox(
                    "Industry domain", domain_names, index=None,
                    placeholder="Pick a domain", key="manual_domain")
                if domain:
                    st.caption(DOMAINS[domain]["description"])
                    companies = st.multiselect(
                        f"Companies (max {usage.MAX_COMPANIES_PER_SEARCH})",
                        DOMAINS[domain]["companies"],
                        default=DOMAINS[domain]["companies"][:usage.MAX_COMPANIES_PER_SEARCH],
                        max_selections=usage.MAX_COMPANIES_PER_SEARCH,
                        key="manual_cos")

        if companies:
            kw_raw = st.text_input(
                "Role keywords (optional)", placeholder="e.g. data engineer, architect",
                max_chars=60)
            days = st.select_slider("Posted within (days)", options=[7, 14, 30], value=14)
            st.markdown("#### Step 3 — Search")

        if st.button("Search", type="primary", disabled=not companies):
            keywords = _sanitize_keywords(kw_raw)
            if st.session_state.get("searches_used", 0) >= usage.MAX_SEARCHES_PER_SESSION:
                st.warning("Session search limit reached — refresh the page to start over.")
            elif not usage.consume_quota(len(companies)):
                st.warning("The demo's daily Adzuna quota is used up — please try again tomorrow.")
            else:
                st.session_state["searches_used"] = st.session_state.get("searches_used", 0) + 1
                usage.log_event("search", domain=domain,
                                companies=companies, keywords=keywords)
                # Query Adzuna by company only — its what= search ANDs every
                # term, so adding role keywords floods results with other
                # companies' jobs that the company post-filter then rejects.
                # Keywords are applied client-side instead (any-token match).
                kw_tokens = keywords.lower().split()
                seen_urls: set[str] = set()
                results = []
                progress = st.progress(0.0, text="Searching…")
                for i, co in enumerate(companies):
                    try:
                        for p in adzuna.fetch(_clean_company(co),
                                              max_days_old=days):
                            text = f"{p.title} {p.description}".lower()
                            if kw_tokens and not any(t in text for t in kw_tokens):
                                continue
                            if p.url not in seen_urls:
                                seen_urls.add(p.url)
                                results.append(p)
                    except Exception as exc:
                        usage.log_event("error", detail=f"adzuna {co}: {str(exc)[:200]}")
                        st.warning(f"{co}: search failed, skipped.")
                    progress.progress((i + 1) / len(companies),
                                      text=f"Searched {co}")
                progress.empty()

                results.sort(key=lambda p: p.posted_date or "", reverse=True)
                # Persist so "Analyse my fit" reruns don't wipe the result list.
                st.session_state["results"] = results
                st.session_state["ai_results"] = {}
                st.session_state["analyses_this_search"] = 0

                # Record to session recent-searches (last 3, newest last).
                recent = st.session_state.setdefault("recent_searches", [])
                recent.append({
                    "time": datetime.now(timezone.utc).strftime("%d %b %H:%M UTC"),
                    "domain": domain,
                    "companies": list(companies),
                    "keywords": keywords,
                    "results": len(results),
                })
                st.session_state["recent_searches"] = recent[-3:]

                # Record to persistent per-user history (best-effort).
                if st.session_state.get("user_hash"):
                    try:
                        search_history.record_search(
                            st.session_state["user_hash"],
                            st.session_state.get("user_name") or "",
                            domain, list(companies), keywords, len(results),
                            email_masked=st.session_state.get("user_email_masked", ""),
                            location=st.session_state.get("user_location", ""))
                    except Exception:
                        pass

        _render_results()

        ai_left = usage.ai_quota_remaining() if config.AI_SCORING_ENABLED else 0
        st.caption(
            f"Demo quota: {usage.quota_remaining()} Adzuna calls left today · "
            f"{usage.MAX_SEARCHES_PER_SESSION - st.session_state.get('searches_used', 0)} "
            f"searches left this session"
            + (f" · {ai_left} AI analyses left today" if config.AI_SCORING_ENABLED else ""))


if tab_about is not None:
    with tab_about:
        st.title("About this project")
        st.markdown(f"""
This demo is the public slice of a **personal agentic job-search pipeline**
built with Python + Claude. The full system runs locally and adds what a
public demo can't:

| Stage | What it does | Where it runs |
|---|---|---|
| **Domain detection** | Resume → industry domain → GCC company shortlist | This demo (keyword heuristic) · Local (Claude reads the full resume) |
| **Sourcing** | Direct ATS connectors (Workday, Oracle ORC, Eightfold, SmartRecruiters, Darwinbox) + Adzuna aggregator + agent web search, routed per company | Local + this demo (Adzuna only) |
| **AI fit scoring** | Each posting scored 0–100 vs the resume, with three hats — HR Director, Hiring Manager, Recruiter — + honest resume tailoring | This demo (Anthropic Haiku, one posting at a time) · Local (Claude headless, every match) |
| **Tailoring** | Emphasise genuinely-relevant points; route real gaps to a "Currently Learning" section, never invented | This demo (per analysed posting) · Local (per strong match, written to a file) |
| **Reporting** | HTML + PDF report emailed twice daily on a schedule | Local (Gmail API + Task Scheduler) |

Source code: [{GITHUB_URL.removeprefix("https://")}]({GITHUB_URL})

### Sample output (fabricated data)
The cards below show the *format* the matcher produces — the data here is
**sample only**. Run a real search and click **Analyse my fit** for live scoring.
""")
        try:
            samples = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))["matches"]
        except Exception:
            samples = []
        for m in samples:
            score = m["fit_score"]
            color = "#2e7d32" if score >= 70 else "#e65100" if score >= 55 else "#616161"
            st.markdown(
                f"**{m['title']}** — {m['company']} · {m['location']} · "
                f"posted {m['posted_date']} · "
                f"<span style='background:{color};color:white;padding:2px 8px;"
                f"border-radius:10px;font-size:0.85em'>FIT {score}</span> · "
                f"<i>{m['source']}</i>",
                unsafe_allow_html=True)
            st.caption(m["rationale"])
            with st.expander("Three-hat verdicts"):
                for hat, v in m["three_hats"].items():
                    st.markdown(f"- **{hat.replace('_', ' ').title()}**: "
                                f"{v['verdict']} — {v['reason']}")
            st.divider()

if tab_admin is not None:
    with tab_admin:
        admin.render()
