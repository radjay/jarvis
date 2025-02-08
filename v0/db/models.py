from .client import supabase
from datetime import datetime, timedelta

# Todos
def add_todo(user_id: str, task: str, completed: bool = False):
    return supabase.table("todos").insert({
        "user_id": user_id,
        "task": task,
        "completed": completed
    }).execute()

def get_todos(user_id: str):
    return supabase.table("todos").select("*").eq("user_id", user_id).execute()

def update_todo(todo_id: int, updates: dict):
    return supabase.table("todos").update(updates).eq("id", todo_id).execute()

def delete_todo(todo_id: int):
    return supabase.table("todos").delete().eq("id", todo_id).execute()

# Calendar Items
def add_calendar_item(user_id: str, title: str, event_date: str, start_time: str = None, end_time: str = None, all_day: bool = False, description: str = "", google_id: str = None):
    return supabase.table("calendar_items").insert({
        "user_id": user_id,
        "title": title,
        "event_date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "all_day": all_day,
        "description": description,
        "google_id": google_id
    }).execute()

def get_calendar_items(user_id: str):
    today = datetime.now().date()
    next_week = today + timedelta(days=7)
    return supabase.table("calendar_items")\
        .select("*")\
        .eq("user_id", user_id)\
        .gte("event_date", str(today))\
        .lte("event_date", str(next_week))\
        .order("event_date", desc=False)\
        .order("start_time", desc=False)\
        .execute()

def update_calendar_item(item_id: int, updates: dict):
    return supabase.table("calendar_items").update(updates).eq("id", item_id).execute()

def delete_calendar_item(item_id: int):
    return supabase.table("calendar_items").delete().eq("id", item_id).execute()

# Messages/Emails
def add_message(user_id: str, subject: str, body: str, unique_id: str, message_type: str = "email", sent: bool = False, important: bool = False):
    return supabase.table("messages").insert({
        "user_id": user_id,
        "subject": subject,
        "body": body,
        "unique_id": unique_id,
        "message_type": message_type,
        "sent": sent,
        "important": important
    }).execute()

def get_messages(user_id: str):
    return supabase.table("messages").select("*").eq("user_id", user_id).execute()

def update_message(message_id: int, updates: dict):
    return supabase.table("messages").update(updates).eq("id", message_id).execute()

def delete_message(message_id: int):
    return supabase.table("messages").delete().eq("id", message_id).execute()

def get_message_by_unique_id(user_id: str, unique_id: str):
    result = supabase.table("messages").select("*").eq("user_id", user_id).eq("unique_id", unique_id).execute()
    if result.data:
        return result.data[0]
    return None

def get_calendar_item_by_google_id(user_id: str, google_id: str):
    result = supabase.table("calendar_items").select("*").eq("user_id", user_id).eq("google_id", google_id).execute()
    if result.data:
        return result.data[0]
    return None

# Simple in‑memory storage for demo purposes.
google_accounts_db = []
_next_google_account_id = 1

def add_google_account(user_id, email, credentials_json):
    global _next_google_account_id
    account = {
        "id": _next_google_account_id,
        "user_id": user_id,
        "email": email,
        "credentials": credentials_json
    }
    _next_google_account_id += 1
    google_accounts_db.append(account)
    return account

def get_google_accounts(user_id):
    return [acct for acct in google_accounts_db if acct["user_id"] == user_id]

def remove_google_account(account_id):
    global google_accounts_db
    google_accounts_db = [acct for acct in google_accounts_db if acct["id"] != account_id]
