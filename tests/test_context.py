import os
import sqlite3
import tempfile

from app import context as memory


def db():
    c=sqlite3.connect(":memory:")
    c.row_factory=sqlite3.Row
    memory.setup(c)
    return c


def test_requires_approval_and_project_scope():
    with db() as c:
        a=memory.create_project(c,"Alpha")
        b=memory.create_project(c,"Beta")
        fid=memory.create_fact(c,a,"labstack uruchamia FastAPI przez systemd")
        assert memory.build_context(c,a,"Jak działa labstack?")["facts"] == []
        assert memory.set_fact_status(c,a,fid,"approved")
        found=memory.build_context(c,a,"Jak działa labstack?")
        assert len(found["facts"]) == 1
        assert "labstack" in found["system_message"]
        assert memory.build_context(c,b,"Jak działa labstack?")["facts"] == []
        assert not memory.set_fact_status(c,b,fid,"rejected")


def test_reject_delete_and_fts():
    with db() as c:
        p=memory.create_project(c,"Projekt")
        a=memory.create_fact(c,p,"Dostęp przez protokół HTTPS")
        b=memory.create_fact(c,p,"Dane testowe architektury")
        memory.set_fact_status(c,p,a,"approved")
        memory.set_fact_status(c,p,b,"approved")
        assert len(memory.retrieve(c,p,"HTTPS")) == 1
        memory.set_fact_status(c,p,a,"rejected")
        assert memory.retrieve(c,p,"HTTPS") == []
        memory.remove_fact(c,p,b)
        assert memory.retrieve(c,p,"architektury") == []


def test_query_syntax_is_safe():
    with db() as c:
        p=memory.create_project(c,"Sandbox")
        fid=memory.create_fact(c,p,'Model "Bielik" dostępny lokalnie')
        memory.set_fact_status(c,p,fid,"approved")
        assert memory.build_context(c,p,'(Bielik OR "something") AND *')["facts"]


def test_endpoint_review_flow(tmp_path, monkeypatch):
    # Keep the app global DB path isolated from other tests.
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "DB", tmp_path / "gateway.db")
    monkeypatch.setenv("GATEWAY_PASSWORD", "test-secret-strong-password")
    h={"X-Gateway-Password": "test-secret-strong-password"}
    with TestClient(main.app) as client:
        p=client.post("/api/projects",headers=h,json={"name":"Labstack"})
        assert p.status_code==201
        pid=p.json()["id"]
        f=client.post(f"/api/projects/{pid}/facts",headers=h,json={"body":"Gemini obsługuje język polski"})
        assert f.status_code==201
        fid=f.json()["id"]
        def preview():
            return client.post("/api/context/preview",headers=h,json={"project_id":pid,"question":"Gemini?"}).json()
        assert preview()["facts"]==[]
        assert client.patch(f"/api/projects/{pid}/facts/{fid}",headers=h,json={"status":"approved"}).status_code==200
        assert len(preview()["facts"])==1
        assert client.patch(f"/api/projects/{pid}/facts/{fid}",headers=h,json={"status":"rejected"}).status_code==200
        assert preview()["facts"]==[]
        assert client.get(f"/api/projects/{pid}/facts").status_code==401
