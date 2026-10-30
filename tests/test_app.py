import os
import tempfile

os.environ["GATEWAY_PASSWORD"] = "test-secret-strong-password"
os.environ["DATABASE_PATH"] = os.path.join(tempfile.gettempdir(), "ai-gateway-lan-test.db")

from fastapi.testclient import TestClient
from app.main import app, conn

HEADERS = {"X-Gateway-Password": "test-secret-strong-password"}

def test_healthz():
    with TestClient(app) as c:
        assert c.get("/healthz").json() == {"status": "ok"}

def test_auth_and_models():
    with TestClient(app) as c:
        assert c.get("/api/models").status_code == 401
        response = c.get("/api/models", headers=HEADERS)
        assert response.status_code == 200
        assert {x["provider"] for x in response.json()} == {"ollama", "openai", "groq", "gemini"}

def test_unknown_provider():
    with TestClient(app) as c:
        r = c.post("/api/chat", headers=HEADERS, json={"provider": "unknown", "message": "hello"})
        assert r.status_code == 400

def test_local_only_blocks_cloud():
    with TestClient(app) as c:
        r = c.post("/api/chat", headers=HEADERS, json={"provider": "openai", "message": "test", "local_only": True})
        assert r.status_code == 403

def test_chat_lifecycle():
    with TestClient(app) as c:
        with conn() as db:
            db.execute("INSERT OR REPLACE INTO chats(id,title) VALUES('example-chat','Example')")
            db.execute("INSERT INTO messages(chat_id,role,content) VALUES('example-chat','user','hello')")
        assert c.get("/api/chats/example-chat", headers=HEADERS).json()[0]["content"] == "hello"
        assert c.delete("/api/chats/example-chat", headers=HEADERS).json() == {"deleted": True}
        assert c.get("/api/chats/example-chat", headers=HEADERS).status_code == 404
