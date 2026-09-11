from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.tools.base_tool import BaseTool
from database import DatabaseManager
import json
import os
import time
import traceback
from collections import deque

# Load .env if present (ignore if python-dotenv not installed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' cdn.tailwindcss.com cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
    "font-src fonts.gstatic.com; "
    "connect-src 'self' ws://localhost:8000 https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "frame-ancestors 'none';"
)

class CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        return response

app = FastAPI()
app.add_middleware(CSPMiddleware)

MAX_PAYLOAD_BYTES = 64_000   # 64 KB raw message cap
MAX_NAME_LEN      = 100
MAX_PROMPT_LEN    = 10_000
MAX_MESSAGE_LEN   = 4_000
RATE_WINDOW       = 10       # seconds per rate window
RATE_MAX_MESSAGES = 20       # max messages per window per connection

ALLOWED_ORIGINS = {
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:8000").split(",")
    if o.strip()
}

db = DatabaseManager()
base_tool = BaseTool()

@app.get("/")
async def get():
    return FileResponse("index.html")

@app.get("/get_agents")
async def get_agents():
    return {"agents": db.fetch_all_agents()}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        print(f"[WS] Rejected connection from origin: {origin!r}")
        return
    await websocket.accept()

    message_times: deque = deque()

    try:
        while True:
            raw_payload = await websocket.receive_text()

            # ── Rate limit ────────────────────────────────────────────────
            now = time.time()
            message_times.append(now)
            while message_times[0] < now - RATE_WINDOW:
                message_times.popleft()
            if len(message_times) > RATE_MAX_MESSAGES:
                await websocket.send_text(json.dumps({"type": "error", "message": "Too many requests. Please slow down."}))
                continue

            # ── Payload size cap ──────────────────────────────────────────
            if len(raw_payload) > MAX_PAYLOAD_BYTES:
                await websocket.send_text(json.dumps({"type": "error", "message": "Message too large."}))
                continue

            data = json.loads(raw_payload)
            request_type = data.get("type")

            # ── 1. CREATE / UPDATE AGENT ──────────────────────────────────
            if request_type == "create_agent":
                agent_id   = data.get("id")
                agent_name = data.get("name") or ""
                system_instructions = data.get("prompt") or ""

                if len(agent_name) > MAX_NAME_LEN:
                    response = {"type": "error", "message": f"Agent name must be {MAX_NAME_LEN} characters or fewer."}
                elif len(system_instructions) > MAX_PROMPT_LEN:
                    response = {"type": "error", "message": f"System prompt must be {MAX_PROMPT_LEN} characters or fewer."}
                elif agent_id:
                    db.update_agent(agent_id, agent_name, system_instructions)
                    response = {"type": "agent_updated", "id": agent_id, "name": agent_name}
                else:
                    new_id = db.save_agent(agent_name, system_instructions)
                    response = {"type": "agent_created", "id": new_id, "name": agent_name}

            # ── 2. RUN AGENT ──────────────────────────────────────────────
            elif request_type == "run_agent":
                agent_id     = data.get("agent_id")
                user_message = data.get("text") or ""

                if len(user_message) > MAX_MESSAGE_LEN:
                    response = {"type": "error", "message": f"Message must be {MAX_MESSAGE_LEN} characters or fewer."}
                    await websocket.send_text(json.dumps(response))
                    continue

                instructions = db.get_agent_prompt(agent_id)

                if instructions:
                    result = base_tool.call_model(system=instructions, user=user_message)
                    if result is None:
                        response = {"type": "error", "message": "AI model unavailable. Check your provider config."}
                    else:
                        db.add_history(agent_id, user_message, result["text"])
                        response = {
                            "type":     "ai_output",
                            "response": result["text"],
                            "tokens":   result["tokens"],
                        }
                else:
                    response = {"type": "error", "message": "Agent not found"}

            # ── 3. GET AGENT DETAILS ──────────────────────────────────────
            elif request_type == "get_agent_details":
                agent_id   = data.get("agent_id")
                agent_data = db.get_agent_details(agent_id)
                if agent_data:
                    response = {
                        "type": "agent_details",
                        "id":     agent_data["id"],
                        "name":   agent_data["name"],
                        "prompt": agent_data["prompt"],
                    }
                else:
                    response = {"type": "error", "message": "Agent not found"}

            # ── 4. GET HISTORY ────────────────────────────────────────────
            elif request_type == "get_history":
                agent_id = data.get("agent_id")
                messages = db.get_history(agent_id)
                response = {"type": "history_data", "messages": messages}

            # ── 5. DELETE AGENT ───────────────────────────────────────────
            elif request_type == "delete_agent":
                agent_id = data.get("agent_id")
                db.delete_agent(agent_id)
                response = {"type": "agent_deleted", "id": agent_id}

            # ── 6. INVALID ────────────────────────────────────────────────
            else:
                response = {"type": "error", "message": "Invalid request type"}

            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Server Error: {e}\n{traceback.format_exc()}")
        await websocket.send_text(json.dumps({"type": "error", "message": "An unexpected error occurred."}))
