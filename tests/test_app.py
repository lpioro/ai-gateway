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


def test_workspace_shell():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        for marker in ("PI-LAB", "themeChoices", "observabilityView", "knowledgeView", "memoryView", "bootstrap-icons"):
            assert marker in r.text


def test_observability_requires_auth_and_counts():
    with TestClient(app) as client:
        assert client.get("/api/observability/summary").status_code == 401
        r = client.get("/api/observability/summary", headers=HEADERS)
        assert r.status_code == 200
        assert set(r.json()) == {"chats", "messages", "projects", "approved_facts", "pending_facts"}
        assert all(isinstance(v, int) and v >= 0 for v in r.json().values())


def test_profiles_create_update_and_filter_chats(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB", tmp_path / "profiles.db")
    with TestClient(main.app) as client:
        assert client.get("/api/profiles").status_code == 401
        initial = client.get("/api/profiles", headers=HEADERS).json()
        assert any(p["id"] == "default" for p in initial)
        r = client.post("/api/profiles", headers=HEADERS, json={"name": "Programista"})
        assert r.status_code == 201
        pid = r.json()["id"]
        profile = {"name": "Programista", "instructions": "Odpowiadaj zwięźle.",
                   "preferred_provider": "openai", "theme": "blue"}
        updated = client.put("/api/profiles/" + pid, headers=HEADERS, json=profile)
        assert updated.status_code == 200
        assert updated.json()["instructions"] == "Odpowiadaj zwięźle."
        bad = client.put("/api/profiles/" + pid, headers=HEADERS,
                         json={**profile, "preferred_provider": "not-real"})
        assert bad.status_code == 422
        with main.conn() as db:
            db.execute("INSERT INTO chats(id,title,profile_id) VALUES(?,?,?)",
                       ("profile-chat","Test",pid))
            db.execute("INSERT INTO chats(id,title) VALUES(?,?)",
                       ("legacy-chat","Legacy"))
        own = client.get("/api/chats", params={"profile_id": pid}, headers=HEADERS)
        assert own.status_code == 200
        assert [chat["id"] for chat in own.json()] == ["profile-chat"]
        legacy = client.get("/api/chats", params={"profile_id":"default"}, headers=HEADERS)
        assert [chat["id"] for chat in legacy.json()] == ["legacy-chat"]
        assert client.get("/api/chats", params={"profile_id":"unknown"}, headers=HEADERS).status_code == 404
        # Existing chat cannot be continued under another profile.
        other = client.post("/api/chat", headers=HEADERS,
                            json={"chat_id":"profile-chat","profile_id":"default",
                                  "provider":"ollama","message":"hello"})
        assert other.status_code == 409


def test_connection_moved_to_sidebar_and_profile_editor():
    with TestClient(app) as client:
        html = client.get("/").text
        assert html.count('id="password"') == 1
        assert html.count('id="connect"') == 1
        assert 'id="connectionPanel"' in html
        assert 'id="profilePicker"' in html
        assert 'id="profilesView"' in html
        assert 'id="profileInstructions"' in html



def test_sidebar_navigation_is_scrollable_and_profile_creation_has_feedback():
    with TestClient(app) as client:
        html = client.get("/").text
        assert "overflow-y:auto;min-height:0;scrollbar-gutter:stable" in html
        assert "Utwórz / edytuj profil" in html
        assert "Podaj nazwę profilu." in html
        assert "Najpierw połącz się z Gateway" in html
        assert "Błąd tworzenia profilu:" in html
