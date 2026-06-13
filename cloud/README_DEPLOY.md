# Deploying the public demo to Streamlit Community Cloud

The cloud app is `cloud_app.py` — a sanitized demo (Adzuna live search +
project showcase + admin page). The full local pipeline (`dashboard.py`,
`run_daily.py`) never goes to the cloud.

## 1. Prerequisites
- The GitHub repo `vijayarajks639-afk/job_search` must be **public** (or
  connected to Streamlit via GitHub auth if private).
- Security review completed and findings fixed (this repo's process requires it
  before every publish).

## 2. Create the app
1. Go to https://share.streamlit.io → **New app**.
2. Repository: `vijayarajks639-afk/job_search`, branch `main`,
   main file path: `cloud_app.py`.
3. Click **Deploy**. First build takes a few minutes.

## 3. Configure secrets
App menu (⋮) → **Settings → Secrets**, paste:

```toml
ADZUNA_APP_ID = "<your adzuna app id>"
ADZUNA_APP_KEY = "<your adzuna app key>"
ADMIN_PASSWORD = "<a long random password — admin tab login>"
GMAIL_ADDRESS = "vijayaraj.ks639@gmail.com"
GMAIL_APP_PASSWORD = "<16-char Gmail app password>"
ANTHROPIC_API_KEY = "<sk-ant-... — powers the 'Analyse my fit' AI scoring>"
```

- **Gmail app password**: create at https://myaccount.google.com/apppasswords
  (requires 2-Step Verification). It is used ONLY to send the on-demand usage
  report; the recipient is hardcoded to vijayaraj.ks639@gmail.com in
  `cloud/admin.py`.
- **Anthropic API key**: create at https://console.anthropic.com/ → API Keys.
  Powers the optional one-posting AI fit-scoring (Haiku). **Cost is capped in
  code** (`cloud/usage.py`): 8 analyses/day, 200/month, 1 per search, 2 per
  session — ~$1–2/month worst case. If you omit this key, the demo still runs;
  the "Analyse my fit" button just doesn't appear (Adzuna search still works).
- **If a secret ever leaks**: revoke the Gmail app password on the same Google
  page (instant); rotate the Anthropic key in the Anthropic console; regenerate
  Adzuna keys at https://developer.adzuna.com/. Then update the Streamlit secrets.

## 4. Local testing (before deploy)
Create `.streamlit/secrets.toml` in the project root with the same keys
(`.streamlit/` is gitignored — never commit it), then:

```
streamlit run cloud_app.py
```

Checks:
- Search tab returns postings for a Banking-domain company pick.
- Admin tab rejects a wrong password, accepts the right one.
- "Email usage report" lands in vijayaraj.ks639@gmail.com.

## 5. Post-deploy smoke test
1. Open the public URL → run a search (e.g. Banking domain, Goldman Sachs + Citi).
2. Log in to Admin → confirm the visit/search counters moved.
3. Send the usage report → confirm receipt.

## Operational notes
- **Storage is ephemeral**: `data/usage.json` and the daily Adzuna quota
  counter reset whenever Community Cloud reboots the app. Acceptable for v1.
- **Quota guard**: 150 Adzuna calls/day global cap, max 5 companies per search,
  3 searches per browser session (`cloud/usage.py`).
- **Resource limits**: Community Cloud gives ~1 GB RAM; this app is well under.
- The app sleeps after inactivity; first visit after sleep takes ~30 s to wake.
