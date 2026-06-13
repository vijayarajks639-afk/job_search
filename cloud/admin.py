"""
Admin tab for the public cloud demo — Vijay only.

- Gate: password from st.secrets["ADMIN_PASSWORD"], compared with
  hmac.compare_digest (no timing leak). Session flag in st.session_state.
- Shows usage summary from cloud.usage + Adzuna quota status.
- "Email usage report" button: SMTP over SSL with a Gmail *app password*
  (st.secrets["GMAIL_ADDRESS"] / st.secrets["GMAIL_APP_PASSWORD"]).
  Recipient is HARDCODED below — the app can never email anyone else.
  App passwords are revocable any time at myaccount.google.com/apppasswords.
"""

from __future__ import annotations

import hmac
import html
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText

import streamlit as st

from cloud import usage

MAX_LOGIN_ATTEMPTS = 5

# Hardcoded by design — usage reports go to the owner only. Do not parameterize.
REPORT_RECIPIENT = "vijayaraj.ks639@gmail.com"


def _check_password(entered: str) -> bool:
    expected = str(st.secrets.get("ADMIN_PASSWORD", ""))
    if not expected:
        return False  # no password configured -> admin disabled
    return hmac.compare_digest(entered.encode(), expected.encode())


def _esc(v) -> str:
    return html.escape(str(v))


def _build_report_html(s: dict) -> str:
    # Escape every interpolated value — company/domain names and error text can
    # carry attacker-influenced content (crafted PDF, Adzuna payload).
    rows_dom = "".join(f"<tr><td>{_esc(d)}</td><td>{_esc(n)}</td></tr>"
                       for d, n in s["top_domains"]) or "<tr><td colspan=2>—</td></tr>"
    rows_co = "".join(f"<tr><td>{_esc(c)}</td><td>{_esc(n)}</td></tr>"
                      for c, n in s["top_companies"]) or "<tr><td colspan=2>—</td></tr>"
    errs = "".join(f"<li>{_esc(e['ts'])} — {_esc(e.get('detail', ''))}</li>"
                   for e in s["last_errors"]) or "<li>none</li>"
    return f"""
    <h2>Job Search Demo — Usage Report</h2>
    <p>Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} ·
       tracking since {_esc(s['since'] or '—')} (resets on app reboot)</p>
    <table border=1 cellpadding=6 cellspacing=0>
      <tr><td>Visits (today / total)</td><td>{s['visits_today']} / {s['visits_total']}</td></tr>
      <tr><td>Searches (today / total)</td><td>{s['searches_today']} / {s['searches_total']}</td></tr>
      <tr><td>Adzuna calls today</td><td>{s['quota_used_today']} / {s['quota_cap']}</td></tr>
      <tr><td>AI analyses (today / month)</td><td>{s['ai_used_today']}/{s['ai_daily_cap']} · {s['ai_used_month']}/{s['ai_monthly_cap']}</td></tr>
      <tr><td>Errors logged</td><td>{s['errors_total']}</td></tr>
    </table>
    <h3>Top domains searched</h3>
    <table border=1 cellpadding=6 cellspacing=0>{rows_dom}</table>
    <h3>Top companies searched</h3>
    <table border=1 cellpadding=6 cellspacing=0>{rows_co}</table>
    <h3>Recent errors</h3><ul>{errs}</ul>
    """


def _send_report(html: str) -> str:
    sender = str(st.secrets.get("GMAIL_ADDRESS", ""))
    app_pw = str(st.secrets.get("GMAIL_APP_PASSWORD", ""))
    if not (sender and app_pw):
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set in secrets")

    msg = MIMEText(html, "html")
    msg["Subject"] = f"Job Search Demo — usage report {datetime.now():%Y-%m-%d %H:%M}"
    msg["From"] = sender
    msg["To"] = REPORT_RECIPIENT

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, app_pw)
        smtp.sendmail(sender, [REPORT_RECIPIENT], msg.as_string())
    return REPORT_RECIPIENT


def render() -> None:
    st.subheader("🔐 Admin")

    if not st.session_state.get("admin_ok"):
        attempts = st.session_state.get("admin_attempts", 0)
        if attempts >= MAX_LOGIN_ATTEMPTS:
            st.error("Too many failed attempts — refresh the page to try again.")
            return
        pw = st.text_input("Admin password", type="password", key="admin_pw_input")
        if st.button("Log in"):
            if _check_password(pw):
                st.session_state["admin_ok"] = True
                st.session_state["admin_attempts"] = 0
                st.rerun()
            else:
                st.session_state["admin_attempts"] = attempts + 1
                time.sleep(1)  # slow down scripted guessing
                st.error("Wrong password.")
        return

    s = usage.summary()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Visits today", s["visits_today"], f"{s['visits_total']} total")
    c2.metric("Searches today", s["searches_today"], f"{s['searches_total']} total")
    c3.metric("Adzuna calls today", f"{s['quota_used_today']}/{s['quota_cap']}")
    c4.metric("AI analyses today", f"{s['ai_used_today']}/{s['ai_daily_cap']}",
              f"{s['ai_used_month']}/{s['ai_monthly_cap']} this month")
    c5.metric("Errors", s["errors_total"])

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Top domains searched**")
        st.table({"domain": [d for d, _ in s["top_domains"]],
                  "searches": [n for _, n in s["top_domains"]]} if s["top_domains"]
                 else {"domain": [], "searches": []})
    with col_b:
        st.markdown("**Top companies searched**")
        st.table({"company": [c for c, _ in s["top_companies"]],
                  "searches": [n for _, n in s["top_companies"]]} if s["top_companies"]
                 else {"company": [], "searches": []})

    if s["last_errors"]:
        with st.expander("Recent errors"):
            for e in s["last_errors"]:
                st.text(f"{e['ts']} — {e.get('detail', '')}")

    st.caption("Stats reset when the app reboots (Community Cloud storage is ephemeral).")

    st.divider()
    if st.button(f"📧 Email usage report to {REPORT_RECIPIENT}"):
        try:
            to = _send_report(_build_report_html(s))
            st.success(f"Usage report sent to {to}.")
        except Exception as exc:
            st.error(f"Email failed: {exc}")

    if st.button("Log out of admin"):
        st.session_state["admin_ok"] = False
        st.rerun()
