import os
import json
from flask import Blueprint, redirect, request, url_for, session, render_template
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime
import requests
from db.models import add_google_account, get_google_accounts, remove_google_account, add_message, get_message_by_unique_id, add_calendar_item, get_calendar_item_by_google_id

GOOGLE_CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secret.json")
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email"
]

google_bp = Blueprint("google", __name__, url_prefix="/google")

@google_bp.route("/connect")
def connect():
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("google.oauth2callback", _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["oauth_state"] = state
    return redirect(authorization_url)

@google_bp.route("/oauth2callback")
def oauth2callback():
    state = session.get("oauth_state")
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for("google.oauth2callback", _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    userinfo_response = requests.get(
        "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
        headers={"Authorization": f"Bearer {creds.token}"}
    )
    userinfo = userinfo_response.json()
    # Try to get email from the userinfo response; if not set, fall back to the id_token.
    email = userinfo.get("email") or (creds.id_token.get("email") if getattr(creds, "id_token", None) else None)

    user_id = request.remote_addr
    add_google_account(user_id, email, creds.to_json())
    return redirect(url_for("google.accounts"))

@google_bp.route("/accounts")
def accounts():
    user_id = request.remote_addr
    accounts = get_google_accounts(user_id)
    return render_template("google_accounts.html", accounts=accounts)

@google_bp.route("/disconnect/<int:account_id>", methods=["POST"])
def disconnect_account(account_id):
    # Optional: Retrieve the account and revoke the token.
    # Example (if you choose to revoke):
    # account = get_google_account_by_id(account_id)
    # if account:
    #     creds_data = json.loads(account["credentials"])
    #     token = creds_data.get("token")
    #     if token:
    #         requests.post(
    #             "https://oauth2.googleapis.com/revoke",
    #             params={"token": token},
    #             headers={"content-type": "application/x-www-form-urlencoded"}
    #         )
    remove_google_account(account_id)
    return redirect(url_for("google.accounts"))

@google_bp.route("/sync")
def sync_page():
    user_id = request.remote_addr
    accounts = get_google_accounts(user_id)
    return render_template("google_sync.html", accounts=accounts)

@google_bp.route("/sync/email/<int:account_id>", methods=["POST"])
def sync_email(account_id):
    user_id = request.remote_addr
    # Locate the account for the current user
    account = None
    for a in get_google_accounts(user_id):
        if a["id"] == account_id:
            account = a
            break
    if not account:
        return redirect(url_for("google.sync_page"))
    
    creds_info = json.loads(account["credentials"])
    creds = Credentials.from_authorized_user_info(creds_info, scopes=SCOPES)
    gmail_service = build("gmail", "v1", credentials=creds)
    response = gmail_service.users().messages().list(userId="me", maxResults=50).execute()
    messages = response.get("messages", [])
    for msg in messages:
        msg_id = msg["id"]
        # Only add if this message hasn't been synced yet.
        if get_message_by_unique_id(user_id, msg_id):
            continue
        full_msg = gmail_service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        label_ids = full_msg.get("labelIds", [])
        is_important = "IMPORTANT" in label_ids
        headers = full_msg.get("payload", {}).get("headers", [])
        subject = ""
        for header in headers:
            if header["name"].lower() == "subject":
                subject = header["value"]
                break
        body = ""
        body_data = full_msg.get("payload", {}).get("body", {}).get("data")
        if body_data:
            import base64
            body = base64.urlsafe_b64decode(body_data.encode("UTF-8")).decode("utf-8", errors="ignore")
        add_message(user_id, subject, body, unique_id=msg_id, message_type="email", important=is_important)
    return redirect(url_for("google.sync_page"))

@google_bp.route("/sync/calendar/<int:account_id>", methods=["POST"])
def sync_calendar(account_id):
    user_id = request.remote_addr
    account = None
    for a in get_google_accounts(user_id):
        if a["id"] == account_id:
            account = a
            break
    if not account:
        return redirect(url_for("google.sync_page"))
    
    creds_info = json.loads(account["credentials"])
    creds = Credentials.from_authorized_user_info(creds_info, scopes=SCOPES)
    calendar_service = build("calendar", "v3", credentials=creds)
    events_result = calendar_service.events().list(calendarId="primary", maxResults=50).execute()
    events = events_result.get("items", [])
    for event in events:
        event_id = event.get("id")
        if get_calendar_item_by_google_id(user_id, event_id):
            continue
        title = event.get("summary", "No Title")
        description = event.get("description", "")
        all_day = False
        start_time = None
        end_time = None
        event_date = ""
        start_info = event.get("start", {})
        end_info = event.get("end", {})
        if "date" in start_info:
            event_date = start_info["date"]
            all_day = True
        elif "dateTime" in start_info:
            dt = start_info["dateTime"]
            event_date = dt.split("T")[0]
            start_time = dt.split("T")[1].split("Z")[0]
            if "dateTime" in end_info:
                dt_end = end_info["dateTime"]
                end_time = dt_end.split("T")[1].split("Z")[0]
        add_calendar_item(user_id, title, event_date, start_time, end_time, all_day, description, google_id=event_id)
    return redirect(url_for("google.sync_page"))