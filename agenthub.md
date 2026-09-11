---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    padding: 52px 68px;
    font-size: 16px;
  }
  section.title {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  h1 { color: #38bdf8; font-size: 2.6rem; margin-bottom: 0.3rem; }
  h2 { color: #7dd3fc; font-size: 1.45rem; border-bottom: 2px solid #1e3a5f; padding-bottom: 10px; margin-bottom: 22px; }
  h3 { color: #a5f3fc; font-size: 1.05rem; margin-top: 1rem; margin-bottom: 0.4rem; }
  code { background: #1e293b; color: #86efac; border-radius: 4px; padding: 2px 7px; font-size: 0.88em; }
  pre { background: #0d1117; border-left: 4px solid #38bdf8; padding: 18px 20px; border-radius: 8px; font-size: 0.8em; line-height: 1.6; }
  ul { margin-left: 1.2rem; }
  ul li { margin-bottom: 7px; line-height: 1.6; }
  strong { color: #fbbf24; }
  em { color: #94a3b8; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
  th { background: #1e3a5f; color: #7dd3fc; padding: 10px 14px; text-align: left; }
  td { padding: 9px 14px; border-bottom: 1px solid #1e293b; vertical-align: top; color: #1e293b; }
  tr:hover td { background: rgba(255,255,255,0.02); }
  blockquote { border-left: 3px solid #6366f1; padding-left: 1rem; color: #94a3b8; font-style: italic; margin: 1rem 0; }
  .tag { display: inline-block; background: #1e3a5f; color: #7dd3fc; border-radius: 6px; padding: 2px 10px; font-size: 0.78em; font-weight: 600; margin-right: 6px; }
---

<!-- _class: title -->

# AgentHub
## Local AI Agent Builder

<br>

> Define a system prompt → give it a name → chat with it instantly.

<br>

*Evolved from `email-drafter-agent` — a single-purpose tool — into a fully generic, reusable AI agent platform.*

---

## 1 · Origin Story — From Email Drafter to AgentHub

### Where it started
- A focused tool called **Email-Drafter-Agent** — given a context, it drafted emails using a local LLM
- Logic was tightly coupled: one agent, one purpose, one tool (`email_tool.py`)

### The problem it revealed
- Users wanted different agents: a SQL expert, a code reviewer, a writing coach…
- Every new use case required changing Python code
- No UI, no persistence, no reusability

### The refactor
- Replaced `App/Agents/` + `email_tool.py` with a **generic `BaseTool`**
- Added a **SQLite database** to persist any number of named agents
- Built a **browser SPA** so non-developers can create and use agents without touching code

> The core insight: a system prompt _is_ the agent. Everything else is infrastructure.

---

## 2 · What is AgentHub?

A **browser-based platform** where anyone can:

1. **Create** a named AI agent by writing a plain-English system prompt
2. **Chat** with that agent in real time inside the browser
3. **Edit or delete** agents at any time
4. **Reload** full conversation history automatically on every session

### The core loop

User writes:  "You are a Python tutor. Explain concepts simply,
show code examples, and never give answers directly."
→ Names it "Python Tutor"
→ Clicks Save

Now they have a persistent, reusable Python Tutor agent
they can chat with from any browser tab — forever.



- No code changes to add a new agent
- No accounts, no cloud, no API key needed by default (Ollama runs locally)
- All data stays on your machine

---

## 3 · Tech Stack

| Layer | Technology | Role |
|---|---|---|
| **Backend** | FastAPI (Python) | HTTP + WebSocket server |
| **Transport** | WebSocket `/ws` | Real-time, bidirectional messaging |
| **Database** | SQLite + `DatabaseManager` | Persist agents & conversation history |
| **LLM Layer** | `BaseTool` (pluggable) | Ollama · OpenAI · Gemini |
| **Frontend** | Single HTML file | Full SPA — no build step |
| **Styling** | Tailwind CSS (CDN) | Utility-first, no config file needed |
| **Markdown** | marked.js (CDN) | Renders AI responses as rich Markdown |

### Python dependencies (`requirements.txt`)
fastapi==0.133.1      uvicorn==0.41.0      websockets==15.0.1
requests==2.32.5      python-dotenv==1.0.1  google-adk==1.25.1



No frontend build step. No `node_modules`. No bundler.

---

## 4 · Frontend — The Single-File SPA

`index.html` is the entire frontend — ~540 lines, zero build tooling.

### UI Layout

┌──────────────────────────────────────────────────────┐
│  Sidebar (dark)          │  Main Panel (light)        │
│  ─────────────────────   │  ─────────────────────     │
│  [A] AgentHub logo       │  Top Bar: agent name +     │
│  [ + New Agent ]  btn    │           edit / delete     │
│  ─────────────────────   │  ─────────────────────     │
│  • Python Tutor   ✎ 🗑  │  Chat messages area        │
│  • SQL Expert     ✎ 🗑  │  (user bubbles right,       │
│  • Email Writer   ✎ 🗑  │   AI bubbles left)          │
│  ─────────────────────   │  ─────────────────────     │
│  ● Connected             │  [ Type a message…  ➤ ]   │
│    localhost:8000         │  Enter to send · Shift+↵  │
└──────────────────────────────────────────────────────┘



### Key UI features
- **Live connection status** — green/yellow/red dot + auto-reconnect every 3 s
- **Typing indicator** — animated 3-dot pulse while AI is responding
- **Token badge** on every AI reply — `prompt in · completion out · total`
- **Copy button** on AI bubbles — copies raw Markdown text
- **Toast notifications** — success / error / info with animated slide-up

---

## 5 · Frontend — WebSocket Client Logic

The JavaScript client (`index.html`) manages all state in-browser.

### Connection & auto-reconnect

```javascript
function connect() {
    ws = new WebSocket("ws://localhost:8000/ws");
    ws.onclose = () => {
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000); // retry in 3 s
    };
    ws.onmessage = handleMessage;
}
window.onload = () => { loadAgentsList(); connect(); };
```

### Message dispatch — clean handler map

```javascript
({
    "agent_created": () => { loadAgentsList(); selectAgent(data.id, data.name); },
    "agent_updated": () => { loadAgentsList(); showView('chatInterface'); },
    "agent_deleted": () => { loadAgentsList(); showView('emptyState'); },
    "history_data":  () => { msgs.forEach(m => appendMessage(...)); },
    "ai_output":     () => { appendMessage('ai', data.response, null, data.tokens); },
    "error":         () => { showToast(data.message, "error"); },
}[data.type] || (() => {}))();
```

Sidebar agents loaded via `GET /get_agents` (REST) on page load, then kept in sync over WebSocket events.

---

## 6 · WebSocket Protocol — Message Types

All communication over `ws://localhost:8000/ws` uses JSON.

| `type` (client → server) | Key fields | Server action |
|---|---|---|
| `create_agent` | `name`, `prompt`, *(optional)* `id` | No `id` → insert; `id` present → update |
| `run_agent` | `agent_id`, `text` | Fetch prompt → call LLM → save history |
| `get_agent_details` | `agent_id` | Return name + system prompt |
| `get_history` | `agent_id` | Return all messages ordered by time |
| `delete_agent` | `agent_id` | Delete agent + CASCADE wipe history |

| `type` (server → client) | Payload |
|---|---|
| `agent_created` / `agent_updated` / `agent_deleted` | `id`, `name` |
| `agent_details` | `id`, `name`, `prompt` |
| `history_data` | `messages[]` — `{user_message, ai_response, timestamp}` |
| `ai_output` | `response` (Markdown text), `tokens {prompt, completion, total}` |
| `error` | `message` string |

---

## 7 · Backend — FastAPI & Request Routing

`main.py` — two REST endpoints + one WebSocket loop.

```python
@app.get("/")            # Serves index.html
@app.get("/get_agents")  # REST: returns [{id, name}, ...] for sidebar

@app.websocket("/ws")
async def websocket_endpoint(websocket):
    await websocket.accept()
    while True:
        data = json.loads(await websocket.receive_text())
        request_type = data.get("type")

        if   request_type == "create_agent":     ...  # db.save_agent / db.update_agent
        elif request_type == "run_agent":         ...  # get_prompt → call_model → add_history
        elif request_type == "get_agent_details": ...
        elif request_type == "get_history":       ...
        elif request_type == "delete_agent":      ...
        else: response = {"type": "error", ...}

        await websocket.send_text(json.dumps(response))
```

Single persistent connection per browser tab. No polling. No REST for chat.

---

## 8 · Database — Schema & Manager

`database.py` wraps a single SQLite connection (`agent_builder.db`).

### Schema

```sql
agents (
    id            TEXT PRIMARY KEY,   -- UUID v4
    name          TEXT UNIQUE,        -- "Python Tutor"
    system_prompt TEXT
)

history (
    id            TEXT PRIMARY KEY,   -- UUID v4
    agent_id      TEXT NOT NULL,
    user_message  TEXT,
    ai_response   TEXT,
    timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
)
```

### Key behaviours
- `ON DELETE CASCADE` — deleting an agent wipes all its history automatically
- **Auto-migration** `_migrate()` — upgrades old schema without data loss
- `check_same_thread=False` — SQLite shared safely across async FastAPI handlers
- `PRAGMA foreign_keys = ON` — enforces cascade at the database level

---

## 9 · LLM Layer — BaseTool & Provider Abstraction

`App/Tools/base_tool.py` — the only file that knows about LLM providers.

### Unified return contract

```python
def call_model(prompt: str) -> dict | None:
    # Always returns:
    { "text": "<AI response>",
      "tokens": { "prompt": int, "completion": int, "total": int } }
    # or None if provider is unreachable / misconfigured
```

`main.py` never sees provider details — calls `call_model()`, checks for `None`.

### Supported providers

| Provider | Default model | Needs key? | Endpoint |
|---|---|---|---|
| **Ollama** | `llama3` | No — local | `localhost:11434/api/generate` |
| **OpenAI** | `gpt-4o-mini` | Yes — `OPENAI_API_KEY` | `api.openai.com/v1/chat/completions` |
| **Gemini** | `gemini-2.0-flash` | Yes — `GEMINI_API_KEY` | `generativelanguage.googleapis.com` |

Also supports any **OpenAI-compatible API** (Azure, Groq, Together AI) via `OPENAI_BASE_URL`.

---

## 10 · Configuration — `.env` Reference

Copy `.env.example` → `.env` and set what you need.

```bash
# LLM Provider
LLM_PROVIDER=ollama          # ollama | openai | gemini
LLM_MODEL=llama3             # blank = use provider default
LLM_TEMPERATURE=0.4          # 0.0 deterministic → 1.0 creative
LLM_TIMEOUT=200              # seconds before giving up

# Ollama (default — no key needed)
OLLAMA_URL=http://localhost:11434

# OpenAI
OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=https://api.openai.com/v1  ← override for Azure/Groq

# Gemini
GEMINI_API_KEY=...
```

> Swap from Ollama to OpenAI: change **one line** (`LLM_PROVIDER=openai`) — no code changes anywhere.

---

## 11 · End-to-End Request Flow

### Creating an agent

```
Browser            WebSocket /ws          main.py          SQLite
  │── { type:"create_agent",                │                 │
  │     name:"SQL Expert",                  │                 │
  │     prompt:"You are..." } ─────────────►│                 │
  │                                         │── save_agent() ─►│
  │                                         │◄── new UUID ─────│
  │◄── { type:"agent_created", id, name } ──│                 │
```

### Running an agent (chat)

```
Browser         WebSocket /ws       main.py    BaseTool     LLM
  │── { type:"run_agent",             │            │          │
  │     agent_id, text } ────────────►│            │          │
  │                                   │── get_agent_prompt() ─┤
  │  (typing indicator)               │── call_model() ──────►│
  │                                   │◄── {text, tokens} ────│
  │                                   │── add_history()        │
  │◄── { type:"ai_output",            │
  │      response, tokens } ──────────│
  │  (renders as Markdown)            │
```

---

## 12 · Key Design Decisions

| Decision | Reasoning |
|---|---|
| **WebSocket-first** | Real-time UX — no polling, single connection per tab |
| **Single HTML file** | Zero build tooling; Tailwind + marked.js from CDN |
| **SQLite** | Zero-ops; UUID PKs; `ON DELETE CASCADE` keeps data clean |
| **Provider abstraction** | Codebase is 100% LLM-agnostic outside `BaseTool` |
| **`SYSTEM/USER` prompt format** | Works across all three providers, no templating |
| **Auto-reconnect (3 s)** | Input disabled with "Reconnecting…" so users always know state |

### Strengths
- **Zero-ops** — SQLite + Ollama = no accounts, no cloud, no infra
- **Persisted history** — every conversation saved; auto-loaded on agent select
- **One env var** to swap LLM providers — no code changes anywhere
- **No build step** — clone, `pip install`, `uvicorn`, done

---

## 13 · Running It Locally

```bash
# 1. Start the LLM backend (Ollama — local & free)
ollama run llama3

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. (Optional) configure a different LLM provider
cp .env.example .env
# Edit .env: set LLM_PROVIDER, LLM_MODEL, and your API key

# 4. Start the server
uvicorn main:app --reload
```

Open **http://localhost:8000** — create your first agent and start chatting.

### To switch to OpenAI or Gemini

```bash
# .env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
```

Restart the server. No code changes needed anywhere.

---

## 14 · Project File Structure

```
email-drafter-agent/
│
├── main.py              ← FastAPI app — WebSocket routing + REST
├── database.py          ← DatabaseManager — SQLite wrapper
├── index.html           ← Entire frontend SPA (single file)
├── requirements.txt     ← Python dependencies
├── .env.example         ← Configuration reference
├── agent_builder.db     ← SQLite DB (auto-created on first run)
│
└── App/
    └── Tools/
        └── base_tool.py ← LLM abstraction (Ollama / OpenAI / Gemini)
```

*`App/Agents/` and `email_tool.py` were removed in the AgentHub refactor — their logic is now fully generalised inside `BaseTool` and `main.py`.*

---

<!-- _class: title -->

# Thank You

### AgentHub — define a prompt, name it, start chatting.

<br>

```bash
uvicorn main:app --reload
```

**→ http://localhost:8000**

<br>

*Built with FastAPI · SQLite · Ollama · Tailwind CSS*
