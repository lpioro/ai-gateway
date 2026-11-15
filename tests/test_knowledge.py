import io
from fastapi.testclient import TestClient
from app import main

HEADERS={"X-Gateway-Password":"test-secret-strong-password"}


def test_knowledge_lifecycle_and_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(main,"DB",tmp_path/"knowledge.db")
    with TestClient(main.app) as c:
        assert c.get("/api/knowledge",params={"project_id":"bad"}).status_code==401
        project=c.post("/api/projects",headers=HEADERS,json={"name":"Dokumentacja"}).json()["id"]
        pasted=c.post("/api/knowledge/paste",headers=HEADERS,json={
            "project_id":project,"title":"Instrukcja systemu",
            "content":"Uruchomienie systemu polega na wystartowaniu usługi systemd. " * 30})
        assert pasted.status_code==201,pasted.text
        sid=pasted.json()["id"]
        assert pasted.json()["status"]=="pending"
        listing=c.get("/api/knowledge",headers=HEADERS,params={"project_id":project})
        assert len(listing.json())==1
        assert listing.json()[0]["chunks"]>=1
        assert c.post("/api/knowledge/search",headers=HEADERS,json={
            "project_id":project,"question":"uruchomienie usługi"}).json()
        before=c.post("/api/context/preview",headers=HEADERS,json={
            "project_id":project,"question":"Jak wygląda uruchomienie systemu?"}).json()
        assert not before["sources"]
        reviewed=c.patch("/api/knowledge/"+sid,headers=HEADERS,params={"project_id":project},
                         json={"status":"approved"})
        assert reviewed.status_code==200
        after=c.post("/api/context/preview",headers=HEADERS,json={
            "project_id":project,"question":"Jak wygląda uruchomienie systemu?"}).json()
        assert after["sources"]
        assert "Instrukcja systemu" in after["system_message"]
        assert c.get("/api/knowledge/"+sid,headers=HEADERS,params={"project_id":project}).json()["text"]
        assert c.delete("/api/knowledge/"+sid,headers=HEADERS,params={"project_id":project}).status_code==200
        assert c.get("/api/knowledge/"+sid,headers=HEADERS,params={"project_id":project}).status_code==404
        after_delete=c.post("/api/context/preview",headers=HEADERS,json={
            "project_id":project,"question":"uruchomienie systemu"}).json()
        assert not after_delete["sources"]


def test_upload_validation_and_project_scoping(tmp_path, monkeypatch):
    monkeypatch.setattr(main,"DB",tmp_path/"files.db")
    with TestClient(main.app) as c:
        pid=c.post("/api/projects",headers=HEADERS,json={"name":"Pliki"}).json()["id"]
        other=c.post("/api/projects",headers=HEADERS,json={"name":"Inny"}).json()["id"]
        response=c.post("/api/knowledge/upload",headers=HEADERS,data={"project_id":pid},
                        files={"file":("notes.md",b"# Procedura\n\nKontrola jakosci magazynu i logistyki.","text/markdown")})
        assert response.status_code==201,response.text
        sid=response.json()["id"]
        assert not c.get("/api/knowledge",headers=HEADERS,params={"project_id":other}).json()
        assert c.get("/api/knowledge/"+sid,headers=HEADERS,params={"project_id":other}).status_code==404
        bad=c.post("/api/knowledge/upload",headers=HEADERS,data={"project_id":pid},
                   files={"file":("run.sh",b"echo forbidden","text/plain")})
        assert bad.status_code==422
        huge=c.post("/api/knowledge/upload",headers=HEADERS,data={"project_id":pid},
                    files={"file":("huge.txt",b"x"*(5*1024*1024+1),"text/plain")})
        assert huge.status_code==413
        assert c.post("/api/knowledge/paste",headers=HEADERS,json={
            "project_id":other,"title":"Bez projektu","content":"xyz"}).status_code==201


def test_pdf_and_docx_text_extraction():
    from docx import Document
    from app import knowledge
    doc=Document()
    doc.add_paragraph("Instrukcja dokumentacji projektu")
    data=io.BytesIO()
    doc.save(data)
    assert "Instrukcja dokumentacji" in knowledge.extract("note.docx",data.getvalue())
    from pypdf import PdfWriter
    pdf=PdfWriter()
    pdf.add_blank_page(width=200,height=200)
    data=io.BytesIO()
    pdf.write(data)
    try:
        knowledge.extract("empty.pdf",data.getvalue())
    except ValueError as exc:
        assert "Brak tekstu" in str(exc)
    else:
        assert False,"PDF bez tekstu powinien być odrzucony"


def test_knowledge_ui():
    with TestClient(main.app) as c:
        html=c.get("/").text
        for marker in ('id="knowledgePaste"','id="knowledgeFile"',
                       'id="knowledgeUpload"','id="knowledgeSources"',
                       'id="knowledgeSearch"','id="knowledgePreview"'):
            assert marker in html
