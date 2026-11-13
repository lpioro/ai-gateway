import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = ROOT / "app" / "static" / "markdown.js"
INDEX = ROOT / "app" / "static" / "index.html"


def test_markdown_renderer_is_served_locally():
    with TestClient(app) as client:
        page = client.get("/")
        asset = client.get("/static/markdown.js")
    assert page.status_code == 200
    assert asset.status_code == 200
    assert 'src="/static/markdown.js"' in page.text
    assert "window.PiLabMarkdown" in asset.text
    assert ".md-body" in page.text
    assert "renderAnswer(s,txt)" in page.text
    assert "scheduleAnswerRender(out,answer)" in page.text
    assert "out.textContent+=ev.content" not in page.text


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_markdown_javascript_syntax():
    subprocess.run(["node", "--check", str(MARKDOWN)], check=True)
    # Extract the inline script to check its syntax as well.
    html = INDEX.read_text(encoding="utf-8")
    inline_script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    subprocess.run(["node", "--check", "--input-type=commonjs"],
                   input=inline_script, text=True, check=True)


def test_markdown_content_never_becomes_raw_html():
    js = MARKDOWN.read_text(encoding="utf-8")
    assert "createTextNode" in js
    assert "textContent" in js
    assert "replaceChildren(fragment)" in js
    assert ".innerHTML" not in js
    assert 'node.rel = "noopener noreferrer"' in js
    assert 'url.protocol === "https:"' in js
