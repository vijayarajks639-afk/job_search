"""
Admin tab for the public cloud demo — owner only.

Access gate: the visitor's resume must contain the owner email
(REPORT_RECIPIENT). cloud_app.py extracts the email on resume upload and sets
st.session_state["admin_ok"] = True when it matches. This tab is not rendered
at all for other visitors — it simply doesn't appear in the tab list.

- "Email usage report" button: SMTP over SSL with a Gmail app password
  (st.secrets["GMAIL_ADDRESS"] / st.secrets["GMAIL_APP_PASSWORD"]).
  Recipient is HARDCODED — the app can never email anyone else.
  App passwords are revocable at myaccount.google.com/apppasswords.
"""

from __future__ import annotations

import hmac
import html
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText

import streamlit as st

from cloud import usage, search_history

MAX_LOGIN_ATTEMPTS = 5


def _check_password(entered: str) -> bool:
    expected = str(st.secrets.get("ADMIN_PASSWORD", ""))
    if not expected:
        return False
    return hmac.compare_digest(entered.encode(), expected.encode())

# Hardcoded by design — reports go to the owner only. Also used in cloud_app.py
# as the identity check: if the uploaded resume's email matches this, admin
# access is granted for the session.
REPORT_RECIPIENT = "vijayaraj.ks639@gmail.com"


def _esc(v) -> str:
    return html.escape(str(v))


def _build_report_html(s: dict) -> str:
    rows_dom = "".join(f"<tr><td>{_esc(d)}</td><td>{_esc(n)}</td></tr>"
                       for d, n in s["top_domains"]) or "<tr><td colspan=2>—</td></tr>"
    rows_co = "".join(f"<tr><td>{_esc(c)}</td><td>{_esc(n)}</td></tr>"
                      for c, n in s["top_companies"]) or "<tr><td colspan=2>—</td></tr>"
    errs = "".join(f"<li>{_esc(e['ts'])} — {_esc(e.get('detail', ''))}</li>"
                   for e in s["last_errors"]) or "<li>none</li>"

    all_users = search_history.get_all_users(days=3)
    if all_users:
        user_rows = "".join(
            f"<tr>"
            f"<td>{_esc(u['name'])}</td>"
            f"<td>{_esc(u.get('email_masked', '—'))}</td>"
            f"<td>{_esc(u.get('location', '—'))}</td>"
            f"<td>{len(u['searches'])}</td>"
            f"<td>{datetime.fromisoformat(u['searches'][0]['ts']).strftime('%d %b %H:%M UTC')}</td>"
            f"</tr>"
            for u in all_users
        )
        users_section = f"""
    <h3>Users active (past 3 days)</h3>
    <table border=1 cellpadding=6 cellspacing=0>
      <tr><th>Name</th><th>Email</th><th>Location</th><th>Searches</th><th>Last active</th></tr>
      {user_rows}
    </table>"""
    else:
        users_section = "<h3>Users active (past 3 days)</h3><p>No user searches recorded.</p>"

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
    {users_section}
    <h3>Recent errors</h3><ul>{errs}</ul>
    """


def _send_report(html_body: str) -> str:
    sender = str(st.secrets.get("GMAIL_ADDRESS", ""))
    app_pw = str(st.secrets.get("GMAIL_APP_PASSWORD", ""))
    if not (sender and app_pw):
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set in secrets")
    msg = MIMEText(html_body, "html")
    msg["Subject"] = f"Job Search Demo — usage report {datetime.now():%Y-%m-%d %H:%M}"
    msg["From"] = sender
    msg["To"] = REPORT_RECIPIENT
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, app_pw)
        smtp.sendmail(sender, [REPORT_RECIPIENT], msg.as_string())
    return REPORT_RECIPIENT


def render() -> None:
    # Tab visibility is gated by resume email match (cloud_app.py sets admin_ok).
    # Content is gated by a second factor: ADMIN_PASSWORD from st.secrets.
    if not st.session_state.get("admin_ok"):
        st.warning("Access denied.")
        return

    st.subheader("🔐 Admin")

    if not st.session_state.get("admin_auth"):
        attempts = st.session_state.get("admin_attempts", 0)
        if attempts >= MAX_LOGIN_ATTEMPTS:
            st.error("Too many failed attempts — refresh the page to try again.")
            return
        st.info("Your identity is confirmed. Enter the admin password to continue.")
        pw = st.text_input("Admin password", type="password", key="admin_pw_input")
        if st.button("Unlock"):
            if _check_password(pw):
                st.session_state["admin_auth"] = True
                st.session_state["admin_attempts"] = 0
                st.rerun()
            else:
                st.session_state["admin_attempts"] = attempts + 1
                time.sleep(1)
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

    # ── Per-user search history (past 3 days) ────────────────────────────────
    st.divider()
    st.markdown("### User search history (past 3 days)")
    all_users = search_history.get_all_users(days=3)
    if not all_users:
        st.caption("No user searches recorded in the past 3 days "
                   "(or history was reset on app reboot).")
    else:
        # ── Summary table ────────────────────────────────────────────────────
        summary_rows = []
        for u in all_users:
            last_ts = datetime.fromisoformat(u["searches"][0]["ts"])
            summary_rows.append({
                "Name": u["name"],
                "Email": u.get("email_masked") or "—",
                "Location": u.get("location") or "—",
                "Searches": len(u["searches"]),
                "Last active (UTC)": last_ts.strftime("%d %b %H:%M"),
            })
        st.table(summary_rows)

        # ── Location chart ───────────────────────────────────────────────────
        from collections import Counter
        loc_counts = Counter(
            u.get("location") or "Unknown" for u in all_users
        )
        if any(loc != "Unknown" for loc in loc_counts):
            st.markdown("**Searches by location**")
            # Build {location: search_count} for the chart
            loc_search_counts: dict[str, int] = {}
            for u in all_users:
                loc = u.get("location") or "Unknown"
                loc_search_counts[loc] = loc_search_counts.get(loc, 0) + len(u["searches"])
            st.bar_chart(loc_search_counts)

        # ── Per-user search detail ───────────────────────────────────────────
        for u in all_users:
            last_ts = datetime.fromisoformat(u["searches"][0]["ts"])
            n = len(u["searches"])
            meta = " · ".join(filter(None, [u.get("email_masked"), u.get("location")]))
            label = (f"**{u['name']}**"
                     + (f" · {meta}" if meta else "")
                     + f" — {n} search{'es' if n != 1 else ''} · "
                     + f"last active {last_ts.strftime('%d %b %H:%M UTC')}")
            with st.expander(label, expanded=False):
                rows = []
                for srv in u["searches"]:
                    ts = datetime.fromisoformat(srv["ts"])
                    cos = ", ".join(srv["companies"][:3])
                    if len(srv["companies"]) > 3:
                        cos += f" +{len(srv['companies']) - 3}"
                    rows.append({
                        "When (UTC)": ts.strftime("%d %b %H:%M"),
                        "Domain": srv["domain"],
                        "Companies": cos,
                        "Keywords": srv["keywords"] or "—",
                        "Results": srv["results"],
                    })
                st.table(rows)

    st.divider()
    if st.button(f"📧 Email usage report to {REPORT_RECIPIENT}"):
        try:
            to = _send_report(_build_report_html(s))
            st.success(f"Usage report sent to {to}.")
        except Exception as exc:
            st.error(f"Email failed: {exc}")

    if st.button("Log out of admin"):
        st.session_state["admin_ok"] = False
        st.session_state["admin_auth"] = False
        st.rerun()
