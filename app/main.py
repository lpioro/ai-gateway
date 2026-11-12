import json
import os
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app import context as memory

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
        memory.setup(c)
        c.execute("""CREATE TABLE IF NOT EXISTS user_profiles (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            instructions TEXT NOT NULL DEFAULT '',
            preferred_provider TEXT NOT NULL DEFAULT 'openai',
            theme TEXT NOT NULL DEFAULT 'graphite',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("INSERT OR IGNORE INTO user_profiles(id,name) VALUES('default','Domyślny')")
        if not any(col[1] == "profile_id" for col in c.execute("PRAGMA table_info(chats)")):
            c.execute("ALTER TABLE chats ADD COLUMN profile_id TEXT NOT NULL DEFAULT 'default'")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chats_profile ON chats(profile_id,created_at)

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
    project_id: str | None = None
    use_context: bool = True
    profile_id: str = 'default'

@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}

@app.get("/")
async def index():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/models", dependencies=[Depends(authenticated)])
async def models():
    return [{"provider": name, "model": p["model"], "configured": bool(os.getenv(p["key"])) if p["key"] else True} for name, p in PROVIDERS.items()]

class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    instructions: str = Field(default="", max_length=3000)
    preferred_provider: str = "openai"
    theme: str = "graphite"

THEMES = {"graphite","paper","blue","forest"}

@app.get("/api/profiles", dependencies=[Depends(authenticated)])
async def profiles():
    with conn() as db:
        return [dict(row) for row in db.execute(
            "SELECT id,name,instructions,preferred_provider,theme FROM user_profiles ORDER BY created_at,id"
        )]

@app.post("/api/profiles", dependencies=[Depends(authenticated)], status_code=201)
async def create_profile(req: ProfileCreate):
    name = req.name.strip()
    if not name:
        raise HTTPException(422,"Profile name cannot be blank")
    pid = str(uuid.uuid4())
    with conn() as db:
        db.execute("INSERT INTO user_profiles(id,name) VALUES(?,?)",(pid,name))
    return {"id":pid,"name":name,"instructions":"","preferred_provider":"openai","theme":"graphite"}

@app.put("/api/profiles/{profile_id}", dependencies=[Depends(authenticated)])
async def update_profile(profile_id: str, req: ProfileUpdate):
    if req.preferred_provider not in PROVIDERS or req.theme not in THEMES or not req.name.strip():
        raise HTTPException(422,"Invalid profile settings")
    with conn() as db:
        updated = db.execute(
            "UPDATE user_profiles SET name=?,instructions=?,preferred_provider=?,theme=? WHERE id=?",
            (req.name.strip(),req.instructions,req.preferred_provider,req.theme,profile_id)
        )
        if not updated.rowcount:
            raise HTTPException(404,"Profile not found")
    return {"id":profile_id,**req.model_dump(),"name":req.name.strip()}

@app.get("/api/observability/summary", dependencies=[Depends(authenticated)])
async def observability_summary():
    """Cheap counts from the local SQLite database, no prompt content or secrets."""
    with conn() as db:
        def count(sql):
            return db.execute(sql).fetchone()[0]
        return {
            "chats": count("SELECT COUNT(*) FROM chats"),
            "messages": count("SELECT COUNT(*) FROM messages"),
            "projects": count("SELECT COUNT(*) FROM projects"),
            "approved_facts": count("SELECT COUNT(*) FROM facts WHERE status='approved'"),
            "pending_facts": count("SELECT COUNT(*) FROM facts WHERE status='pending'"),
        }

@app.get("/api/chats", dependencies=[Depends(authenticated)])
async def chats(profile_id: str | None = Query(default=None)):
    with conn() as c:
        if profile_id is not None:
            if not c.execute("SELECT 1 FROM user_profiles WHERE id=?", (profile_id,)).fetchone():
                raise HTTPException(404,"Profile not found")
            return [dict(r) for r in c.execute(
                "SELECT * FROM chats WHERE profile_id=? ORDER BY created_at DESC, rowid DESC LIMIT 100",
                (profile_id,)
            )]
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


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class FactCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    source: str = Field(default="manual", max_length=120)

class FactReview(BaseModel):
    status: str

class ContextPreview(BaseModel):
    project_id: str
    question: str = Field(min_length=1, max_length=25000)

@app.get("/api/projects", dependencies=[Depends(authenticated)])
async def list_projects():
    with conn() as c:
        return [dict(row) for row in c.execute("SELECT id,name,created_at FROM projects ORDER BY created_at DESC")]

@app.post("/api/projects", dependencies=[Depends(authenticated)], status_code=201)
async def new_project(req: ProjectCreate):
    with conn() as c:
        pid=memory.create_project(c,req.name)
    return {"id":pid,"name":req.name.strip()}

@app.get("/api/projects/{project_id}/facts", dependencies=[Depends(authenticated)])
async def facts(project_id: str):
    with conn() as c:
        if not memory.project_exists(c,project_id):
            raise HTTPException(404,"Project not found")
        return memory.fetch_facts(c,project_id)

@app.post("/api/projects/{project_id}/facts", dependencies=[Depends(authenticated)], status_code=201)
async def propose_fact(project_id: str, req: FactCreate):
    with conn() as c:
        if not memory.project_exists(c,project_id):
            raise HTTPException(404,"Project not found")
        fid=memory.create_fact(c,project_id,req.body,req.source)
    return {"id":fid,"status":"pending"}

@app.patch("/api/projects/{project_id}/facts/{fact_id}", dependencies=[Depends(authenticated)])
async def review_fact(project_id: str, fact_id: str, req: FactReview):
    if req.status not in ("approved","rejected","pending"):
        raise HTTPException(400,"Unknown review status")
    with conn() as c:
        if not memory.set_fact_status(c,project_id,fact_id,req.status):
            raise HTTPException(404,"Fact not found")
    return {"id":fact_id,"status":req.status}

@app.delete("/api/projects/{project_id}/facts/{fact_id}", dependencies=[Depends(authenticated)])
async def delete_fact(project_id: str, fact_id: str):
    with conn() as c:
        if not memory.remove_fact(c,project_id,fact_id):
            raise HTTPException(404,"Fact not found")
    return {"deleted":True}

@app.post("/api/context/preview", dependencies=[Depends(authenticated)])
async def preview_context(req: ContextPreview):
    with conn() as c:
        if not memory.project_exists(c,req.project_id):
            raise HTTPException(404,"Project not found")
        return memory.build_context(c,req.project_id,req.question)

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
    context_message = None
    if req.project_id and req.use_context:
        with conn() as c:
            if not memory.project_exists(c,req.project_id):
                raise HTTPException(404,"Project not found")
            context_message=memory.build_context(c,req.project_id,req.message)["system_message"]
    with conn() as c:
        profile = c.execute(
            "SELECT instructions FROM user_profiles WHERE id=?", (req.profile_id,)
        ).fetchone()
        if profile is None:
            raise HTTPException(404,"Profile not found")
        instructions = profile["instructions"]
    cid = req.chat_id or str(uuid.uuid4())
    with conn() as c:
        exists = c.execute("SELECT profile_id FROM chats WHERE id=?", (cid,)).fetchone()
        if exists and exists["profile_id"] != req.profile_id:
            raise HTTPException(409,"Chat belongs to a different profile")
        if req.chat_id and not exists:
            raise HTTPException(404, "Chat not found")
        if not exists:
            c.execute("INSERT INTO chats(id,title,profile_id) VALUES(?,?,?)", (cid, req.message[:75],req.profile_id))
        history = [dict(r) for r in c.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 40", (cid,))]
        history.reverse()
        c.execute("INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)", (cid, "user", req.message))
    history.append({"role": "user", "content": req.message})
    if context_message:
        history.insert(0, {"role":"system","content":context_message})
    if instructions:
        history.insert(0, {"role":"system","content":"Preferencje aktywnego profilu użytkownika (instrukcje):\n"+instructions})

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
