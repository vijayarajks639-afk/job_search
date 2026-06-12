"""
Gmail authentication for the job-search reporter.

Reuses the OAuth client + token from the gmail_cleanup project (copied in as
credentials.json / token.json). The granted `gmail.modify` scope is sufficient to
send mail, so no new browser consent is required. If the token is ever missing or
its scopes are revoked, running this file performs a one-time consent.

Usage:
    python auth.py     # verify / refresh the token, print the connected account
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

# gmail.modify authorises users.messages.send (per Gmail API scope table).
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_gmail_service():
    creds = None
    token = str(config.GMAIL_TOKEN)
    if os.path.exists(token):
        creds = Credentials.from_authorized_user_file(token, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.GMAIL_CREDENTIALS):
                raise FileNotFoundError(
                    f"{config.GMAIL_CREDENTIALS} not found — copy it from the "
                    "gmail_cleanup project or download from Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.GMAIL_CREDENTIALS), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


if __name__ == "__main__":
    svc = get_gmail_service()
    profile = svc.users().getProfile(userId="me").execute()
    print(f"Authenticated as: {profile['emailAddress']}")
