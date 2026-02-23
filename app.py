from flask import Flask, render_template, request, jsonify
import json
import re
from datetime import datetime

app = Flask(__name__)

# ─── Load Faculty Data ─────────────────────────────────────────────────────────
with open("faculty.json", "r", encoding="utf-8") as f:
    faculty_data = json.load(f)

# ─── Chat History (MongoDB with JSON file fallback) ──────────────────────────
from db import save_message, get_history, get_sessions, clear_history, clear_all_history
MONGO_AVAILABLE = True  # db.py handles fallback internally

# ─── RAG Engine (semantic search) ─────────────────────────────────────────────
try:
    from rag_engine import build_faculty_embeddings, hybrid_search as rag_hybrid_search
    build_faculty_embeddings(faculty_data)
    RAG_AVAILABLE = True
    print("[RAG] Semantic search engine ready.")
except Exception as e:
    RAG_AVAILABLE = False
    print(f"[RAG] RAG engine not available ({e}). Using keyword search only.")

# ─── Pre-build a flat search index for speed ──────────────────────────────────
# Each entry: { "keyword": str, "faculty_id": str, "weight": int }
search_index = []

for faculty in faculty_data:
    fid = faculty["id"]
    base_weight = faculty.get("priority_weight", 5)

    # Core subjects = highest weight (x3)
    for subj in faculty.get("core_subjects", []):
        for token in subj.lower().split():
            if len(token) >= 2:
                search_index.append({"keyword": token, "id": fid, "weight": base_weight * 3})
        search_index.append({"keyword": subj.lower(), "id": fid, "weight": base_weight * 3})

    # Synonym tags = high weight (x2)
    for tag in faculty.get("synonym_tags", []):
        search_index.append({"keyword": tag.lower(), "id": fid, "weight": base_weight * 2})
        # Also index individual words in multi-word tags
        for word in tag.lower().split():
            if len(word) >= 3:
                search_index.append({"keyword": word, "id": fid, "weight": base_weight})

    # Research areas = medium weight
    for area in faculty.get("research_areas", []):
        search_index.append({"keyword": area.lower(), "id": fid, "weight": base_weight})
        for word in area.lower().split():
            if len(word) >= 4:
                search_index.append({"keyword": word, "id": fid, "weight": base_weight - 2})

    # Name = for direct name queries
    search_index.append({"keyword": faculty["name"].lower(), "id": fid, "weight": base_weight * 4})
    for word in faculty["name"].lower().split():
        search_index.append({"keyword": word, "id": fid, "weight": base_weight * 3})

    # Department
    search_index.append({"keyword": faculty["department"].lower(), "id": fid, "weight": base_weight})

# ─── Intent Detection ──────────────────────────────────────────────────────────
GREETINGS    = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "howdy", "namaste", "hii", "helo"]
FAREWELLS    = ["bye", "goodbye", "see you", "take care", "exit", "quit", "cya", "see ya", "later"]
THANKS       = ["thank", "thanks", "thank you", "thx", "appreciated", "helpful", "great help", "tysm"]
LIST_QUERIES = ["list all", "show all", "all faculty", "all professors", "all teachers", "faculty list", "show faculty", "who are the faculty"]

def detect_intent(text):
    t = text.lower().strip()
    if any(t == g or t.startswith(g + " ") or t.startswith(g + "!") for g in GREETINGS):
        return "greeting"
    if any(g in t for g in GREETINGS) and len(t.split()) <= 4:
        return "greeting"
    if any(f in t for f in FAREWELLS):
        return "farewell"
    if any(k in t for k in THANKS):
        return "thanks"
    if any(q in t for q in LIST_QUERIES):
        return "list_all"
    return "query"

def normalize(text):
    # Lowercase, remove punctuation except + and #
    text = text.lower()
    text = re.sub(r"[^\w\s\+#]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ─── Stop words (common English words to ignore in search) ─────────────────
STOP_WORDS = {
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must", "need", "dare",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "about", "between", "through", "after", "before", "above",
    "and", "but", "or", "nor", "not", "no", "so", "if", "then", "than",
    "that", "this", "these", "those", "what", "which", "who", "whom",
    "how", "when", "where", "why", "all", "each", "every", "any", "some",
    "very", "just", "also", "too", "more", "most", "much", "many",
    "help", "want", "tell", "know", "find", "get", "give", "make", "take",
    "come", "go", "see", "look", "meet", "today", "tomorrow", "yesterday",
    "now", "here", "there", "please", "thanks", "thank", "hi", "hello",
    "morning", "evening", "afternoon", "night", "time", "day", "week",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "urgently", "urgent", "soon", "immediately", "quickly", "asap",
    "someone", "anyone", "everybody", "something", "anything",
    "am", "pm", "ok", "okay",
}

# ─── Core Matching Engine ──────────────────────────────────────────────────────
def find_faculty(user_input):
    normalized = normalize(user_input)
    tokens = [t for t in normalized.split() if t not in STOP_WORDS and len(t) >= 2]

    if not tokens:
        return []

    # Score each faculty
    scores = {}  # faculty_id -> score

    for entry in search_index:
        kw = entry["keyword"]
        fid = entry["id"]
        weight = entry["weight"]

        # Exact phrase match in full input (for multi-word keywords)
        if " " in kw and kw in normalized:
            scores[fid] = scores.get(fid, 0) + weight

        # Individual token match
        elif len(kw) >= 3:
            for token in tokens:
                if token == kw:
                    scores[fid] = scores.get(fid, 0) + weight // 2
                    break
                # Partial token match — only for long, specific keywords
                elif len(kw) >= 6 and len(token) >= 5 and (kw.startswith(token) or token in kw):
                    scores[fid] = scores.get(fid, 0) + weight // 4
                    break
        # Short keyword exact match (e.g., "c++", "ai", "os", "sql")
        elif len(kw) >= 2:
            for token in tokens:
                if token == kw:
                    scores[fid] = scores.get(fid, 0) + weight
                    break

    if not scores:
        return []

    # Filter out low-quality matches (minimum score threshold)
    min_score = 10
    scores = {fid: s for fid, s in scores.items() if s >= min_score}

    if not scores:
        return []

    # Build sorted result list
    faculty_map = {f["id"]: f for f in faculty_data}
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results = [(score, faculty_map[fid]) for fid, score in ranked if score > 0]
    return results

# ─── Smart Search (hybrid keyword + RAG) ──────────────────────────────────────
def smart_search(user_input):
    """Use hybrid RAG search if available, otherwise fall back to keyword search."""
    keyword_results = find_faculty(user_input)

    if RAG_AVAILABLE:
        try:
            return rag_hybrid_search(user_input, keyword_results, top_k=5)
        except Exception as e:
            print(f"[RAG] Hybrid search failed: {e}. Falling back to keyword search.")

    return keyword_results

# ─── Response Builder ──────────────────────────────────────────────────────────
def build_faculty_payload(faculty, score, rank=1):
    days = ", ".join(faculty.get("available_days", []))
    modes = ", ".join(faculty.get("consultation_modes", []))
    subjects = faculty.get("core_subjects", [])
    tags_sample = faculty.get("synonym_tags", [])[:8]  # show top 8 tags as sample

    confidence = "high" if score >= 40 else "medium" if score >= 15 else "low"

    return {
        "id": faculty["id"],
        "name": faculty["name"],
        "designation": faculty["designation"],
        "department": faculty["department"],
        "core_subjects": subjects,
        "tags_sample": tags_sample,
        "experience": f"{faculty.get('experience_years', '?')} years",
        "qualification": faculty.get("qualification", ""),
        "research_areas": faculty.get("research_areas", []),
        "email": faculty["email"],
        "phone": faculty.get("phone", "N/A"),
        "cabin": faculty["cabin"],
        "available_days": days,
        "available_time": faculty.get("available_time", "N/A"),
        "consultation_modes": modes,
        "profile_summary": faculty.get("profile_summary", ""),
        "confidence": confidence,
        "score": score,
        "rank": rank
    }

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_input = data.get("question", "").strip()
    session_id = data.get("session_id", "default")
    timestamp = datetime.now().strftime("%H:%M")

    if not user_input:
        return jsonify({"type": "error", "reply": "Please type something.", "timestamp": timestamp})

    # Save user message to history
    if MONGO_AVAILABLE:
        try:
            save_message(session_id, "user", user_input)
        except Exception as e:
            print(f"[DB] Failed to save user message: {e}")

    intent = detect_intent(user_input)

    if intent == "greeting":
        reply_data = {
            "type": "greeting",
            "reply": "Hello! 👋 I'm your Faculty Assistant. Ask me about any subject — C++, AI, VLSI, Networks, Embedded Systems — and I'll instantly connect you with the right professor.",
            "timestamp": timestamp
        }
        _save_bot_response(session_id, reply_data)
        return jsonify(reply_data)

    if intent == "farewell":
        reply_data = {
            "type": "farewell",
            "reply": "Goodbye! Come back anytime you need faculty guidance. 👋",
            "timestamp": timestamp
        }
        _save_bot_response(session_id, reply_data)
        return jsonify(reply_data)

    if intent == "thanks":
        reply_data = {
            "type": "thanks",
            "reply": "You're welcome! Feel free to ask about any subject or faculty member. 😊",
            "timestamp": timestamp
        }
        _save_bot_response(session_id, reply_data)
        return jsonify(reply_data)

    if intent == "list_all":
        all_faculty = [
            {
                "name": f["name"],
                "designation": f["designation"],
                "department": f["department"],
                "core_subjects": f["core_subjects"],
                "cabin": f["cabin"],
                "email": f["email"]
            }
            for f in faculty_data
        ]
        reply_data = {
            "type": "list_all",
            "faculty_list": all_faculty,
            "timestamp": timestamp
        }
        _save_bot_response(session_id, reply_data)
        return jsonify(reply_data)

    # ── Main search (hybrid RAG + keyword)
    results = smart_search(user_input)

    if not results:
        # Build subject suggestions from all faculty
        all_subjects = []
        for f in faculty_data:
            all_subjects.extend(f.get("core_subjects", []))
        suggestions = list(set(all_subjects))[:6]

        reply_data = {
            "type": "not_found",
            "reply": "I couldn't find a faculty match for that topic. Try asking about a specific subject like 'C++', 'Machine Learning', 'VLSI', 'OS', or 'Embedded Systems'.",
            "suggestions": suggestions,
            "timestamp": timestamp
        }
        _save_bot_response(session_id, reply_data)
        return jsonify(reply_data)

    top_score, top_faculty = results[0]
    primary = build_faculty_payload(top_faculty, top_score, rank=1)

    # Include up to 2 alternate matches if they scored reasonably
    alternates = []
    for score, fac in results[1:3]:
        if score >= 8 and fac["id"] != top_faculty["id"]:
            alternates.append({
                "name": fac["name"],
                "department": fac["department"],
                "core_subjects": fac["core_subjects"],
                "cabin": fac["cabin"],
                "email": fac["email"]
            })

    reply_data = {
        "type": "faculty",
        "faculty": primary,
        "alternates": alternates,
        "timestamp": timestamp
    }
    _save_bot_response(session_id, reply_data)
    return jsonify(reply_data)


def _save_bot_response(session_id, reply_data):
    """Helper to save bot response to history."""
    try:
        bot_text = reply_data.get("reply", "")
        if not bot_text and reply_data.get("type") == "faculty":
            bot_text = f"Found: {reply_data['faculty']['name']}"
        save_message(session_id, "bot", bot_text, response_data=reply_data)
    except Exception as e:
        print(f"[DB] Failed to save bot response: {e}")


# ─── History Routes ───────────────────────────────────────────────────────────
@app.route("/history", methods=["GET"])
def history_sessions():
    """Get all chat sessions."""
    try:
        sessions = get_sessions()
        return jsonify(sessions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/history/<session_id>", methods=["GET"])
def history_messages(session_id):
    """Get all messages for a specific session."""
    try:
        messages = get_history(session_id)
        return jsonify(messages)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/history/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """Delete a specific chat session."""
    try:
        clear_history(session_id)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/history", methods=["DELETE"])
def delete_all_history():
    """Clear all chat history."""
    try:
        clear_all_history()
        return jsonify({"status": "cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/faculty", methods=["GET"])
def list_faculty():
    return jsonify([
        {
            "id": f["id"],
            "name": f["name"],
            "designation": f["designation"],
            "department": f["department"],
            "core_subjects": f["core_subjects"],
            "cabin": f["cabin"],
            "email": f["email"],
            "available_time": f.get("available_time", ""),
            "profile_summary": f.get("profile_summary", "")
        }
        for f in faculty_data
    ])

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "faculty_count": len(faculty_data),
        "index_size": len(search_index),
        "mongo_available": MONGO_AVAILABLE,
        "rag_available": RAG_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    app.run(debug=True)
