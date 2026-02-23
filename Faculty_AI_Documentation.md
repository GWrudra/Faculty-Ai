# Faculty AI — Complete Project Documentation

> A comprehensive guide explaining every part of the Faculty AI chatbot project in simple words.

---

## 📁 Project Structure

```
faculty_ai/
├── app.py              ← Backend (the brain)
├── faculty.json        ← Data file (the phone book)
├── index.html          ← Standalone frontend (not used by Flask)
└── templates/
    └── index.html      ← Main frontend served by Flask (the face)
```

---

---

# 📄 File 1: `faculty.json` — The Data File

## What is this file?

`faculty.json` is a **data file** — like a digital phone book for professors. It stores all information about each faculty member in a format called **JSON**.

## What is JSON?

**JSON** = JavaScript Object Notation. A way to store data that both humans and computers can read easily.

## The Structure

- `[ ... ]` — **Square brackets** = a **list** (array) of items. Each item is one faculty member.
- `{ ... }` — **Curly braces** = an **object** holding key-value pairs (like a form with labels and answers).

## Each Field Explained

| Field | What it means |
|---|---|
| `"id": "FAC001"` | A unique ID, like a roll number |
| `"name"` | The professor's name |
| `"designation"` | Job title (Professor, Associate Professor) |
| `"department"` | Which department they belong to |
| `"core_subjects"` | Main subjects they teach (as a list `[]`) |
| `"synonym_tags"` | Keywords the chatbot matches your question against. e.g., "pointers" or "linked list" matches to the C++ professor |
| `"experience_years"` | Years of teaching (a number, no quotes) |
| `"qualification"` | Their highest degree |
| `"research_areas"` | Topics they research |
| `"email"` | Email address |
| `"phone"` | Phone number |
| `"cabin"` | Physical location (room number) |
| `"available_days"` | Days available for consultation |
| `"available_time"` | Time slot they're free |
| `"consultation_modes"` | How to reach them — in person, online, or email |
| `"priority_weight"` | Ranking score — higher = shows up first when multiple professors match |
| `"profile_summary"` | Short bio paragraph |

## JSON Data Types Used

- **Strings** (text) → in `"quotes"` → `"Dr. Rakesh Sharma"`
- **Numbers** → no quotes → `18`
- **Lists/Arrays** → use `[]` → `["Monday", "Tuesday"]`
- **Objects** → use `{}` → the entire faculty block

## The 5 Professors

| # | Name | Teaches |
|---|---|---|
| 1 | Dr. Rakesh Sharma | C++, Data Structures |
| 2 | Dr. Anjali Mehta | AI, Machine Learning |
| 3 | Dr. Vivek Rao | Microprocessors, Embedded Systems |
| 4 | Dr. Priya Nair | Operating Systems, Computer Networks |
| 5 | Dr. Arvind Kulkarni | VLSI, Electronics |

---

---

# 📄 File 2: `app.py` — The Backend (Brain)

The server that processes questions and finds the right professor.

---

## 1. Imports (Line 1-4)

```python
from flask import Flask, render_template, request, jsonify
import json, re
from datetime import datetime
```

- **Flask** = Python framework that turns your code into a web server
- **json** = reads the `faculty.json` file
- **re** = Regular Expressions — cleans up text (removes punctuation, etc.)
- **datetime** = gets current time for timestamps

---

## 2. Create the App (Line 6)

```python
app = Flask(__name__)
```

One line creates the entire web server. Flask makes it that simple.

---

## 3. Load Faculty Data (Line 9-10)

```python
with open("faculty.json", "r") as f:
    faculty_data = json.load(f)
```

Opens the JSON file and reads all 5 professors into a Python list.

---

## 4. Search Index (Line 14-48)

Builds a **big keyword list** for fast searching, like a book's index at the back.

| What gets indexed | Weight (importance) |
|---|---|
| Professor's **name** | Highest (×4) |
| **Core subjects** (c++, ai) | Very high (×3) |
| **Synonym tags** (pointers, oop) | High (×2) |
| **Research areas** | Medium (×1) |
| **Department** | Low (×1) |

**Weight** = how important a match is. Name matches score highest.

---

## 5. Intent Detection (Line 51-68)

Before searching, the bot checks: **what does the user want?**

| If user types... | Intent | What happens |
|---|---|---|
| "hi", "hello" | `greeting` | Sends welcome message |
| "bye", "exit" | `farewell` | Says goodbye |
| "thanks" | `thanks` | Says you're welcome |
| "list all faculty" | `list_all` | Shows all professors |
| Anything else | `query` | Searches for a professor |

---

## 6. Normalize (Line 70-75)

Cleans up what you type:
- Makes everything **lowercase** ("C++" → "c++")
- Removes **punctuation** ("who teaches C++?" → "who teaches c++")
- Removes **extra spaces**

---

## 7. Find Faculty — The Core Search Engine (Line 78-112)

1. Takes your cleaned-up question
2. Compares every word against the search index
3. **Scores** each professor based on how many keywords match
4. Returns professors **sorted by score** (best match first)

**Match types:**
- **Exact match** = full score ("machine learning" finds "machine learning")
- **Token match** = half score ("learning" matches individual word)
- **Partial match** = quarter score ("thread" matches "multithreading")

---

## 8. Build Faculty Payload (Line 115-143)

Packages a professor's info into a neat response. Adds a **confidence badge**:
- Score ≥ 40 → ✅ **High** confidence
- Score ≥ 15 → 🟡 **Medium**
- Score < 15 → 🔴 **Low**

---

## 9. Routes (Line 146-266)

Routes = URLs your app responds to. Like doors to different rooms.

| Route | Method | What it does |
|---|---|---|
| `/` | GET | Shows the chat page |
| `/ask` | POST | Receives question, returns answer |
| `/faculty` | GET | Returns list of all professors (for sidebar) |
| `/health` | GET | Checks if server is running |

---

## 10. Start the Server (Line 265-266)

```python
if __name__ == "__main__":
    app.run(debug=True)
```

Starts on `http://127.0.0.1:5000`. `debug=True` = auto-restarts when you save changes.

---

---

# 📄 File 3: `templates/index.html` — The Frontend (Face)

What the user sees and interacts with. Has 3 parts: **HTML** (structure), **CSS** (styling), **JavaScript** (logic).

---

## Part 1: HTML — The Structure

### Sidebar (Left Panel)

```
┌──────────────────┐
│ 🎓 FacultyAI     │  ← Logo
│ ✦ New Conversation│  ← Reset button
│ ─── Directory ───│
│ • Dr. Rakesh      │  ← Clickable faculty chips
│ • Dr. Anjali      │     (loaded from /faculty API)
│ • Dr. Vivek       │
│ ───────────────── │
│ 🟢 System Online  │  ← Status indicator
└──────────────────┘
```

### Main Area (Right Side)

```
┌─────────────────────────────────┐
│ Faculty Assistant  [Engine v3]  │ ← Topbar
├─────────────────────────────────┤
│        🎓 How can I help?       │ ← Welcome screen
│   [ML] [C++] [VLSI] [IoT] [OS] │ ← Quick prompt buttons
│                                 │
│  🧑 "who teaches ai?"     (you)│ ← User bubble
│  🎓 [Faculty Card]        (bot)│ ← Bot reply
├─────────────────────────────────┤
│ [Type your question...    ] [➤] │ ← Input area
└─────────────────────────────────┘
```

---

## Part 2: CSS — The Styling

### CSS Variables (`:root`)

```css
--bg: #0a0a0f;      /* Deep dark background */
--accent: #6c63ff;   /* Purple accent color */
--accent2: #00d4aa;  /* Teal/green accent */
```

Variables = reusable colors. Change one value → changes the entire theme.

### Key Styling Concepts

| Concept | What it does | Example |
|---|---|---|
| `flexbox` | Arranges items in rows/columns | Sidebar + Main side by side |
| `border-radius` | Rounds corners | Rounded chat bubbles |
| `linear-gradient` | Blends 2+ colors | Purple-to-teal buttons |
| `backdrop-filter: blur()` | Frosted glass effect | Topbar looks like glass |
| `@keyframes` | Creates animations | Bouncing typing dots |
| `transition` | Smooth hover effects | Buttons lift on hover |
| `overflow-y: auto` | Adds scrollbar when needed | Chat area scrolls |
| `@media` | Responsive design | Sidebar hides on phones |

---

## Part 3: JavaScript — The Logic

### Key Functions

| Function | What it does |
|---|---|
| `loadFaculty()` | Calls `/faculty` API → fills sidebar with professor names |
| `sendMessage()` | Takes your input → sends to `/ask` → shows response |
| `handleResponse()` | Routes the answer to the right display function |
| `renderFacultyCard()` | Builds the rich card with all professor details |
| `renderListAll()` | Displays all faculty as a scrollable list |
| `appendUser()` | Shows your message as a purple bubble (right side) |
| `appendBotText()` | Shows bot reply as a dark bubble (left side) |
| `appendTyping()` | Shows bouncing dots "..." while waiting for response |
| `esc()` | Escapes HTML characters to prevent code injection |
| `getTime()` | Returns current time like "04:30 PM" |
| `autoResize()` | Makes textarea grow as you type more lines |
| `handleKey()` | Enter = send, Shift+Enter = new line |
| `clearChat()` | Resets chat back to welcome screen |
| `toggleSidebar()` | Opens/closes sidebar on mobile |

---

---

# 🔌 All 4 APIs Explained

## What is an API?

**API** = Application Programming Interface. Like a **waiter** — the frontend places an order, the API carries it to the backend, and brings back the response.

---

### API 1: `GET /` — Serve the Page

| Detail | Value |
|---|---|
| **Defined in** | `app.py` line 146-148 |
| **Called by** | Browser when you visit `http://127.0.0.1:5000` |
| **What it does** | Returns the `templates/index.html` page |

---

### API 2: `POST /ask` — The Main Chatbot API ⭐

| Detail | Value |
|---|---|
| **Defined in** | `app.py` line 150-237 |
| **Called by** | `sendMessage()` in JavaScript |
| **Sends** | `{ "question": "your question" }` |
| **Returns** | JSON based on intent type |

**The JavaScript fetch call:**

```javascript
const res = await fetch("/ask", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question })
});
```

**All 7 possible response types:**

| Type | When | Example |
|---|---|---|
| `greeting` | You say "hi" | `{ type: "greeting", reply: "Hello!..." }` |
| `farewell` | You say "bye" | `{ type: "farewell", reply: "Goodbye!..." }` |
| `thanks` | You say "thank you" | `{ type: "thanks", reply: "You're welcome!" }` |
| `faculty` | You ask about a subject | `{ type: "faculty", faculty: {...}, alternates: [...] }` |
| `list_all` | You say "show all" | `{ type: "list_all", faculty_list: [...] }` |
| `not_found` | No match found | `{ type: "not_found", suggestions: [...] }` |
| `error` | Empty input | `{ type: "error", reply: "Please type something." }` |

---

### API 3: `GET /faculty` — Faculty List

| Detail | Value |
|---|---|
| **Defined in** | `app.py` line 239-254 |
| **Called by** | `loadFaculty()` in JavaScript |
| **What it does** | Returns simplified list of all professors |
| **Used for** | Populating the sidebar chips |

---

### API 4: `GET /health` — Health Check

| Detail | Value |
|---|---|
| **Defined in** | `app.py` line 256-263 |
| **Called by** | Not called by frontend — for monitoring/DevOps |
| **Returns** | `{ status: "ok", faculty_count: 5 }` |

---

### API Flow Diagram

```
Page loads in browser
    │
    ├── GET /          → serves the HTML page
    │
    └── GET /faculty   → loads sidebar with professor names

User types and hits Enter
    │
    └── POST /ask      → sends question, gets answer back

Admin/DevOps checking
    │
    └── GET /health    → "yep, server is running!"
```

---

---

# 🔄 How Everything Connects — The Full Picture

```
You type "C++ pointers" and press Enter
         │
         ▼
    [JavaScript] sendMessage()
         │
         ▼ (POST /ask with JSON body)
    [Flask app.py] receives the question
         │
         ▼
    detect_intent() → "query"
         │
         ▼
    normalize() → "c++ pointers"
         │
         ▼
    find_faculty() → searches index → Dr. Rakesh scores 30
         │
         ▼
    build_faculty_payload() → packages response as JSON
         │
         ▼ (JSON response sent back)
    [JavaScript] handleResponse()
         │
         ▼
    renderFacultyCard() → displays the beautiful faculty card
```

---

## Important Notes

- **No external APIs used!** Everything runs locally — the search engine, matching, and scoring are all custom Python code.
- The project uses **Flask** (Python) for the backend and **vanilla HTML/CSS/JS** for the frontend.
- **No database** — all data comes from `faculty.json` loaded into memory at startup.

---

> *Document generated on 23 February 2026*
> *Faculty AI — Smart Faculty Assistant Project*
