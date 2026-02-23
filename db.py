"""
db.py — Chat history storage for Faculty AI.

Strategy:
  1. Try connecting to MongoDB (if available)
  2. If not, fall back to a local JSON file (chat_history.json)
  This ensures chat history always works, even without MongoDB installed.
"""

import json
import os
from datetime import datetime

# ─── Try MongoDB first ─────────────────────────────────────────────────────────
_mongo_available = False
_db = None

try:
    from pymongo import MongoClient, DESCENDING
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    _client.admin.command("ping")  # actual connectivity test
    _db = _client["faculty_ai"]
    _db.chat_messages.create_index([("session_id", 1), ("timestamp", 1)])
    _db.chat_sessions.create_index([("session_id", 1)], unique=True)
    _db.chat_sessions.create_index([("updated_at", -1)])
    _mongo_available = True
    print("[DB] MongoDB connected successfully.")
except Exception as e:
    print(f"[DB] MongoDB not available ({e}). Using local JSON file storage.")

# ─── JSON File Fallback ───────────────────────────────────────────────────────
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_history.json")


def _load_json():
    """Load chat history from the JSON file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"sessions": {}, "messages": {}}
    return {"sessions": {}, "messages": {}}


def _save_json(data):
    """Save chat history to the JSON file."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Unified API (works with both MongoDB and JSON file) ─────────────────────

def save_message(session_id, role, content, response_data=None):
    """Save a chat message."""
    now = datetime.utcnow()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    if _mongo_available:
        _mongo_save_message(session_id, role, content, response_data, now)
    else:
        _json_save_message(session_id, role, content, response_data, now_str)


def get_history(session_id):
    """Get all messages for a session, sorted by time."""
    if _mongo_available:
        return _mongo_get_history(session_id)
    else:
        return _json_get_history(session_id)


def get_sessions(limit=20):
    """Get recent chat sessions with preview text."""
    if _mongo_available:
        return _mongo_get_sessions(limit)
    else:
        return _json_get_sessions(limit)


def clear_history(session_id):
    """Delete a specific session and its messages."""
    if _mongo_available:
        _mongo_clear_history(session_id)
    else:
        _json_clear_history(session_id)


def clear_all_history():
    """Delete all chat history."""
    if _mongo_available:
        _mongo_clear_all()
    else:
        _json_clear_all()


# ─── JSON File Implementations ────────────────────────────────────────────────

def _json_save_message(session_id, role, content, response_data, now_str):
    data = _load_json()

    # Upsert session
    if session_id not in data["sessions"]:
        title = content[:50] if role == "user" else "New Chat"
        data["sessions"][session_id] = {
            "session_id": session_id,
            "title": title,
            "created_at": now_str,
            "updated_at": now_str,
        }
    else:
        data["sessions"][session_id]["updated_at"] = now_str

    # Append message
    if session_id not in data["messages"]:
        data["messages"][session_id] = []

    msg = {
        "role": role,
        "content": content,
        "timestamp": now_str,
    }
    if response_data:
        msg["response_data"] = response_data

    data["messages"][session_id].append(msg)
    _save_json(data)


def _json_get_history(session_id):
    data = _load_json()
    messages = data.get("messages", {}).get(session_id, [])
    # Format timestamps for display
    result = []
    for msg in messages:
        m = dict(msg)
        # Extract just HH:MM from the timestamp
        try:
            dt = datetime.strptime(m["timestamp"], "%Y-%m-%d %H:%M:%S")
            m["timestamp"] = dt.strftime("%H:%M")
        except (ValueError, KeyError):
            pass
        result.append(m)
    return result


def _json_get_sessions(limit):
    data = _load_json()
    sessions = list(data.get("sessions", {}).values())
    # Sort by updated_at descending
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    # Format timestamps for display
    for s in sessions[:limit]:
        try:
            dt = datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M:%S")
            s["created_at"] = dt.strftime("%b %d, %H:%M")
        except (ValueError, KeyError):
            pass
        try:
            dt = datetime.strptime(s["updated_at"], "%Y-%m-%d %H:%M:%S")
            s["updated_at"] = dt.strftime("%b %d, %H:%M")
        except (ValueError, KeyError):
            pass
    return sessions[:limit]


def _json_clear_history(session_id):
    data = _load_json()
    data["sessions"].pop(session_id, None)
    data["messages"].pop(session_id, None)
    _save_json(data)


def _json_clear_all():
    _save_json({"sessions": {}, "messages": {}})


# ─── MongoDB Implementations ─────────────────────────────────────────────────

def _mongo_save_message(session_id, role, content, response_data, now):
    session_title = content[:50] if role == "user" else None

    _db.chat_sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {"updated_at": now},
            "$setOnInsert": {
                "session_id": session_id,
                "title": session_title or "New Chat",
                "created_at": now,
            },
        },
        upsert=True,
    )

    message = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": now,
    }
    if response_data:
        message["response_data"] = response_data

    _db.chat_messages.insert_one(message)


def _mongo_get_history(session_id):
    messages = list(
        _db.chat_messages.find(
            {"session_id": session_id},
            {"_id": 0, "session_id": 0},
        ).sort("timestamp", 1)
    )
    for msg in messages:
        msg["timestamp"] = msg["timestamp"].strftime("%H:%M")
    return messages


def _mongo_get_sessions(limit):
    sessions = list(
        _db.chat_sessions.find({}, {"_id": 0})
        .sort("updated_at", -1)
        .limit(limit)
    )
    for s in sessions:
        s["created_at"] = s["created_at"].strftime("%b %d, %H:%M")
        s["updated_at"] = s["updated_at"].strftime("%b %d, %H:%M")
    return sessions


def _mongo_clear_history(session_id):
    _db.chat_messages.delete_many({"session_id": session_id})
    _db.chat_sessions.delete_one({"session_id": session_id})


def _mongo_clear_all():
    _db.chat_messages.delete_many({})
    _db.chat_sessions.delete_many({})
