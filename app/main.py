import json
import os
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()
ROOT = Path(__file__).resolve().parent
DB = Path(os.getenv("DATABASE_PATH", str(ROOT.parent / "gateway.db")))
PROVIDERS = {
    "ollama": {"url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/v1/chat/completions", "key": None, "model": os.getenv("OLLAMA_MODEL", "qwen3:4b")},
    "openai": {"url": "https://api.openai.com/v1/chat/completions", "key": "OPENAI_API_KEY", "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini")},
    "groq": {"url": "https://api.groq.com/openai/v1/chat/completions", "key": "GROQ_API_KEY", "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")},
    "gemini": {"url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "key": "GEMINI_API_KEY", "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash")},
}

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="AI Gateway LAN", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

async def authenticated(x_gateway_password: str | None = Header(default=None)):
    password = os.getenv("GATEWAY_PASSWORD", "")
    if not password or password == "change-me-before-lan":
        raise HTTPException(503, "Configure a strong GATEWAY_PASSWORD")
    if not x_gateway_password or not secrets.compare_digest(password, x_gateway_password):
        raise HTTPException(401, "Invalid gateway password")

class ChatRequest(BaseModel):
    chat_id: str | None = None
    provider: str = "ollama"
    message: str = Field(min_length=1, max_length=25000)
    local_only: bool = False

@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}

@app.get("/")
async def index():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/models", dependencies=[Depends(authenticated)])
async def models():
    return [{"provider": name, "model": p["model"], "configured": bool(os.getenv(p["key"])) if p["key"] else True} for name, p in PROVIDERS.items()]

@app.get("/api/chats", dependencies=[Depends(authenticated)])
async def chats():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM chats ORDER BY created_at DESC, rowid DESC LIMIT 100")]

@app.get("/api/chats/{chat_id}", dependencies=[Depends(authenticated)])
async def messages(chat_id: str):
    with conn() as c:
        if not c.execute("SELECT 1 FROM chats WHERE id=?", (chat_id,)).fetchone():
            raise HTTPException(404, "Chat not found")
        return [dict(r) for r in c.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id", (chat_id,))]

@app.delete("/api/chats/{chat_id}", dependencies=[Depends(authenticated)])
async def delete_chat(chat_id: str):
    with conn() as c:
        if not c.execute("SELECT 1 FROM chats WHERE id=?", (chat_id,)).fetchone():
            raise HTTPException(404, "Chat not found")
        c.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    return {"deleted": True}

@app.post("/api/chat", dependencies=[Depends(authenticated)])
async def chat(req: ChatRequest):
    if req.provider not in PROVIDERS:
        raise HTTPException(400, "Unknown provider")
    if (req.local_only or os.getenv("FORCE_LOCAL_ONLY", "").lower() in ("true", "1", "yes")) and req.provider != "ollama":
        raise HTTPException(403, "Cloud providers disabled in local-only mode")
    cfg = PROVIDERS[req.provider]
    key = os.getenv(cfg["key"]) if cfg["key"] else "local"
    if not key:
        raise HTTPException(400, "Provider API key not configured")
    cid = req.chat_id or str(uuid.uuid4())
    with conn() as c:
        exists = c.execute("SELECT 1 FROM chats WHERE id=?", (cid,)).fetchone()
        if req.chat_id and not exists:
            raise HTTPException(404, "Chat not found")
        if not exists:
            c.execute("INSERT INTO chats(id,title) VALUES(?,?)", (cid, req.message[:75]))
        history = [dict(r) for r in c.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 40", (cid,))]
        history.reverse()
        c.execute("INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)", (cid, "user", req.message))
    history.append({"role": "user", "content": req.message})

    async def stream():
        yield "data: " + json.dumps({"type": "chat_id", "chat_id": cid}) + "\n\n"
        answer = ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
                async with client.stream("POST", cfg["url"], headers={"Authorization": f"Bearer {key}"}, json={"model": cfg["model"], "messages": history, "stream": True}) as response:
                    if response.status_code >= 400:
                        raise RuntimeError(f"Provider HTTP {response.status_code}: check model, key and limits")
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        if raw == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw).get("choices", [{}])[0].get("delta", {}).get("content") or ""
                        except (ValueError, IndexError, TypeError):
                            continue
                        if chunk:
                            answer += chunk
                            yield "data: " + json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False) + "\n\n"
            if answer:
                with conn() as c:
                    c.execute("INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)", (cid, "assistant", answer))
            yield "data: " + json.dumps({"type": "done"}) + "\n\n"
        except (httpx.HTTPError, RuntimeError) as exc:
            msg = "Provider connection failed" if isinstance(exc, httpx.HTTPError) else str(exc)
            yield "data: " + json.dumps({"type": "error", "message": msg}) + "\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
