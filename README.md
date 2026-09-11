# AgentHub

A browser-based platform for creating, running, and managing custom AI agents. Define an agent with a system prompt, then chat with it — all in a clean web UI backed by Ollama, OpenAI, or Gemini.

## Project Structure

```
email-drafter-agent/
├── app/
│   └── tools/
│       └── base_tool.py    # LLM client (Ollama / OpenAI / Gemini)
├── database.py             # SQLite DatabaseManager (agents + history)
├── main.py                 # FastAPI server & WebSocket handler
├── index.html              # Single-file SPA (Tailwind CSS + marked.js + DOMPurify)
├── agent_builder.db         # SQLite database (auto-created on first run)
├── .env.example             # Sample environment configuration
└── requirements.txt
```

## Getting Started

**Prerequisites:** at least one LLM provider configured — [Ollama](https://ollama.com) running locally (default), or an OpenAI/Gemini API key.

1. Clone the repo and create a virtual environment:

   ```bash
   git clone <repo-url> email-drafter-agent
   cd email-drafter-agent
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables (optional — defaults to Ollama):

   ```bash
   cp .env.example .env
   ```

   See [Configuration](#configuration) below for available variables.

4. If using Ollama, pull and run the model:

   ```bash
   ollama run llama3
   ```

   Ollama must be reachable at `http://localhost:11434` (or `OLLAMA_URL`).

5. Start the server:

   ```bash
   uvicorn main:app --reload
   ```

   Open `http://localhost:8000/` in your browser.

## Configuration

Set these via `.env` (loaded automatically) or the shell environment:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | One of `ollama`, `openai`, `gemini` |
| `LLM_MODEL` | provider default (`llama3` / `gpt-4o-mini` / `gemini-2.0-flash`) | Model name for the selected provider |
| `LLM_TEMPERATURE` | `0.4` | Sampling temperature |
| `LLM_TIMEOUT` | `200` | Request timeout (seconds) |
| `OLLAMA_URL` | `http://localhost:11434` | Base URL of the Ollama instance |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint override |
| `GEMINI_API_KEY` | — | Required when `LLM_PROVIDER=gemini` |
| `ALLOWED_ORIGINS` | `http://localhost:8000` | Comma-separated list of origins allowed to open the WebSocket |

## Features

- Create custom agents with any system prompt
- Edit and delete existing agents
- Chat with any agent in real time over WebSocket
- Conversation history persisted per agent in SQLite, with per-agent cascade delete
- Switch LLM provider (Ollama, OpenAI, Gemini) via environment config — no code changes
- Markdown rendering of AI responses, sanitized with DOMPurify
- Responsive sidebar listing all your agents

## How It Works

**Request flow:**
1. Browser connects over WebSocket (`/ws`) — rejected unless its `Origin` header is in `ALLOWED_ORIGINS`
2. Frontend sends JSON with a `type` field
3. `main.py` routes by type → calls `DatabaseManager` or `BaseTool`
4. Response JSON is sent back over the same socket

**WebSocket message types:**

| Type | Description |
|---|---|
| `create_agent` | Create a new agent (no `id`) or update an existing one (with `id`) |
| `run_agent` | Send a user message to an agent; gets AI response + token usage back |
| `get_agent_details` | Fetch an agent's name and system prompt by ID |
| `get_history` | Fetch an agent's full conversation history |
| `delete_agent` | Remove an agent and its full conversation history |

Each connection is rate-limited (20 messages / 10s window) and payloads are capped (64 KB per message, 100 chars for names, 10,000 for prompts, 4,000 for chat messages). Requests outside these limits get an `error` response instead of being processed.

There is also a REST endpoint `GET /get_agents` that returns all agents (used by the sidebar on page load).

**LLM layer** (`app/tools/base_tool.py`):  
`BaseTool` dispatches to Ollama, OpenAI, or Gemini based on `LLM_PROVIDER`, sending the agent's system prompt and the user's message separately (`call_model(system, user)`) and returning `{"text": ..., "tokens": {"prompt", "completion", "total"}}`.

**Database** (`database.py`):  
`DatabaseManager` wraps a single SQLite connection, guarded by a lock for thread-safe access. Two tables:
- `agents(id, name, system_prompt)`
- `history(id, agent_id, user_message, ai_response, timestamp)` — `agent_id` is a foreign key into `agents(id)` with `ON DELETE CASCADE`, so deleting an agent removes its history automatically.

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.133.1 | Web framework & REST API |
| `uvicorn` | 0.41.0 | ASGI server |
| `websockets` | 15.0.1 | WebSocket support |
| `requests` | 2.32.5 | HTTP calls to Ollama/OpenAI/Gemini |
| `python-dotenv` | 1.2.1 | Loads `.env` for local configuration |

## Customization

- **Switch LLM provider/model:** Set `LLM_PROVIDER` and `LLM_MODEL` in `.env` (see [Configuration](#configuration)) — no code changes needed.
- **Adjust temperature / timeout:** Set `LLM_TEMPERATURE` / `LLM_TIMEOUT` in `.env`, or edit the defaults in `app/tools/base_tool.py`.
- **Adjust rate limits / payload caps:** Edit the constants at the top of `main.py` (`RATE_WINDOW`, `RATE_MAX_MESSAGES`, `MAX_PAYLOAD_BYTES`, `MAX_NAME_LEN`, `MAX_PROMPT_LEN`, `MAX_MESSAGE_LEN`).

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b ft/your-feature`)
3. Commit your changes
4. Open a pull request

## License

MIT License — see `LICENSE` for details.
