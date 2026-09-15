from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_root_serves_creation_interface() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<form id="link-form"' in response.text
    assert 'name="url"' in response.text
    assert 'name="custom_alias"' in response.text
    assert 'role="status"' in response.text
    assert 'id="copy-button"' in response.text
    assert 'id="open-link"' in response.text


def test_ui_assets_are_served() -> None:
    client = TestClient(create_app(Settings()))

    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/app.js")

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert 'fetch("/api/v1/links"' in script.text
    assert "payload.custom_alias = customAlias" in script.text
    assert "textContent" in script.text
    assert "innerHTML" not in script.text
