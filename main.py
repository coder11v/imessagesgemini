#!/usr/bin/env python3
"""
imessage_gemini_catchup.py

Usage:
  - DB mode (automated): python imessage_gemini_catchup.py --mode db --chat-name "My Group Chat" --last 80
  - Clipboard mode (manual selection): Select messages in Messages.app, then run:
       python imessage_gemini_catchup.py --mode clipboard
Requirements:
  - Python 3.10+
  - pip install google-genai python-dateutil
  - Export GEMINI_API_KEY in env
Notes:
  - Replace MODEL_ID with your desired Gemini model (e.g. "gemini-2.5-flash" or "gemini-3-pro")
  - Uses the google-genai library for clean API interaction
"""
import os
import argparse
import sqlite3
import subprocess
from datetime import datetime, timedelta
from dateutil import tz
from google import genai
import sys
from typing import List

# ---------- CONFIG ----------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")  # change if you want
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Default DB path on macOS
DEFAULT_CHAT_DB = os.path.expanduser("~/Library/Messages/chat.db")
# ----------------------------

if not GEMINI_API_KEY:
    print("ERROR: Set GEMINI_API_KEY environment variable with your Gemini API key.")
    sys.exit(1)

# Initialize Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

def mac_time_to_datetime(mac_seconds):
    """
    Convert Mac absolute time (seconds since 2001-01-01) to Python datetime in local timezone.
    If input is None or 0, return None.
    """
    try:
        if mac_seconds is None:
            return None
        # Some DBs store as integer milliseconds or use other units; attempt to handle:
        # If value looks too big (> 10**11), treat as microseconds/milliseconds and scale down.
        s = float(mac_seconds)
        # heuristic scaling
        if s > 1e12:  # microseconds
            s = s / 1_000_000
        elif s > 1e10:  # milliseconds
            s = s / 1000
        # Mac epoch: 2001-01-01
        mac_epoch = datetime(2001, 1, 1, tzinfo=tz.tzutc())
        dt = mac_epoch + timedelta(seconds=s)
        return dt.astimezone(tz.tzlocal())
    except Exception:
        return None

def fetch_messages_from_db(db_path: str, chat_name: str, limit=200) -> List[dict]:
    """
    Reads chat.db and returns messages for the chat with display_name == chat_name.
    Returns list of dicts: [{sender, text, date, service, is_from_me}, ...]
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Chat DB not found at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Query to find the chat rowid(s) that match the display_name.
    # chat.display_name is often what you see in Messages.app.
    cur.execute("SELECT ROWID, guid, display_name FROM chat WHERE display_name = ?", (chat_name,))
    chat_rows = cur.fetchall()
    if not chat_rows:
        # attempt fuzzy match by GUID or group name substring
        cur.execute("SELECT ROWID, guid, display_name FROM chat WHERE display_name LIKE ?", (f"%{chat_name}%",))
        chat_rows = cur.fetchall()
    if not chat_rows:
        raise ValueError(f"No chat found matching '{chat_name}'. Try an exact display name or check DB path.")

    chat_rowids = [r["ROWID"] for r in chat_rows]

    # Now join chat_message_join -> message and handle to get sender info
    placeholders = ",".join(["?"] * len(chat_rowids))
    query = f"""
    SELECT
      m.ROWID as message_rowid,
      m.text,
      m.date,
      m.is_from_me,
      h.id as handle_id,
      m.service
    FROM message m
    JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
    JOIN chat c ON c.ROWID = cmj.chat_id
    LEFT JOIN handle h ON m.handle_id = h.ROWID
    WHERE cmj.chat_id IN ({placeholders})
    ORDER BY m.date DESC
    LIMIT ?
    """
    params = chat_rowids + [limit]
    cur.execute(query, params)

    rows = cur.fetchall()
    messages = []
    for r in rows[::-1]:  # reverse to chronological ascending
        dt = mac_time_to_datetime(r["date"])
        messages.append({
            "message_rowid": r["message_rowid"],
            "text": r["text"],
            "date": dt.isoformat() if dt else None,
            "is_from_me": bool(r["is_from_me"]),
            "handle": r["handle_id"],
            "service": r["service"],
        })
    conn.close()
    return messages

def clipboard_messages_via_osascript() -> str:
    """
    Uses osascript to copy the current selection in Messages.app to the clipboard,
    then returns clipboard contents. You must manually select messages in Messages.app first.
    """
    # This AppleScript: press cmd+c (copy) then read clipboard
    applescript = r'''
    tell application "System Events"
        -- send Cmd+C to copy selection (Messages must be frontmost and selection present)
        keystroke "c" using {command down}
    end tell
    delay 0.15
    set theClipboard to the clipboard
    return theClipboard
    '''
    p = subprocess.run(["osascript", "-e", applescript], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"osascript failed: {p.stderr.strip()}")
    return p.stdout

def gemini_summarize(messages: List[dict]) -> str:
    """
    Send messages to Gemini to request a compact catch-up summary.
    Uses the google-genai library for clean interaction.
    """
    # Create a prompt that guides Gemini to summarize
    combined_text = ""
    for m in messages:
        ts = m.get("date") or ""
        sender = "Me" if m.get("is_from_me") else (m.get("handle") or "Unknown")
        text = m.get("text") or ""
        # small cleaning
        combined_text += f"[{ts}] {sender}: {text}\n"

    system_instruction = (
        "You are an assistant that reads an iMessage group chat export and returns a compact, bullet-point 'catch-up' summary.\n"
        "Output structure:\n"
        "1) 6-12 bullet points summarizing what happened (decisions, dates, plans, action items, drama/highlights).\n"
        "2) A short 'Who said what' section listing notable speakers and their short positions.\n"
        "3) Explicit list of action items with assignees and deadlines (if present in text).\n"
        "Be concise and only include what is contained in the messages. Use ISO dates when present."
    )

    prompt = "Here is the chat export:\n\n" + combined_text + "\n\n" + system_instruction

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    return response.text

def main():
    global GEMINI_MODEL
    ap = argparse.ArgumentParser(prog="imessage_gemini_catchup.py")
    ap.add_argument("--mode", choices=["db", "clipboard"], default="db")
    ap.add_argument("--chat-name", help="display name of the iMessage group chat (used in DB mode)")
    ap.add_argument("--db-path", default=DEFAULT_CHAT_DB, help="Path to chat.db (DB mode)")
    ap.add_argument("--last", type=int, default=150, help="How many last messages to fetch (DB mode)")
    ap.add_argument("--model", default=GEMINI_MODEL, help="Gemini model id")
    args = ap.parse_args()

    GEMINI_MODEL = args.model

    try:
        if args.mode == "db":
            if not args.chat_name:
                raise ValueError("DB mode requires --chat-name 'Group Chat Name'")
            messages = fetch_messages_from_db(args.db_path, args.chat_name, limit=args.last)
            if not messages:
                print("No messages found.")
                return
            print(f"Fetched {len(messages)} messages from DB for '{args.chat_name}'. Preparing request...")
            summary = gemini_summarize(messages)
            print("\n=== CATCH-UP SUMMARY ===\n")
            print(summary)
        else:
            print("Clipboard mode: please select the messages in Messages.app, then press Enter to continue.")
            input("Press Enter after selecting (and ensuring Messages.app is frontmost)...")
            clip = clipboard_messages_via_osascript()
            # make a simple parsed messages list: split lines and send to Gemini
            messages = [{"text": line, "date": None, "is_from_me": False, "handle": "unknown"} for line in clip.splitlines() if line.strip()]
            print(f"Captured {len(messages)} lines from clipboard. Sending to Gemini...")
            summary = gemini_summarize(messages)
            print("\n=== CATCH-UP SUMMARY ===\n")
            print(summary)

    except Exception as e:
        print("ERROR:", e)
        raise

if __name__ == "__main__":
    main()
