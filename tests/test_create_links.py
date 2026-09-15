from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import get_session
from app.main import create_app
from app.models import Base


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    application = create_app(Settings(public_base_url="https://short.example/links/"))

    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    with TestClient(application) as test_client:
        yield test_client
    engine.dispose()


def test_creates_automatic_alias(client: TestClient) -> None:
    response = client.post("/api/v1/links", json={"url": "https://example.com/a?q=1"})

    assert response.status_code == 201
    body = response.json()
    assert len(body["alias"]) == 10
    assert body["alias"].isalnum()
    assert body["alias"] == body["alias"].lower()
    assert body["original_url"] == "https://example.com/a?q=1"
    assert body["short_url"] == f"https://short.example/links/{body['alias']}"
    assert body["is_custom"] is False
    assert body["click_count"] == 0
    assert body["last_accessed_at"] is None
    assert body["id"]
    assert body["created_at"]
    assert response.headers["location"] == f"/api/v1/links/{body['alias']}"


def test_creates_custom_alias(client: TestClient) -> None:
    response = client.post(
        "/api/v1/links",
        json={"url": "http://example.com", "custom_alias": "my-link"},
    )

    assert response.status_code == 201
    assert response.json()["alias"] == "my-link"
    assert response.json()["is_custom"] is True


@pytest.mark.parametrize(
    ("url", "custom_alias"),
    [
        ("ftp://example.com/file", None),
        ("/relative", None),
        ("https://user:password@example.com", None),
        ("https:///missing-host", None),
        ("https://example.com/has a space", None),
        ("https://example.com", "UPPER"),
        ("https://example.com", "a"),
        ("https://example.com", "ab"),
        ("https://example.com", "-starts-wrong"),
        ("https://example.com", "ends-wrong-"),
        ("https://example.com", "has_underscore"),
        ("https://example.com", "a" * 33),
        ("https://example.com", "api"),
        ("https://example.com", "health"),
        ("https://example.com", "ready"),
        ("https://example.com", "docs"),
        ("https://example.com", "redoc"),
    ],
)
def test_rejects_invalid_input(client: TestClient, url: str, custom_alias: str | None) -> None:
    payload = {"url": url}
    if custom_alias is not None:
        payload["custom_alias"] = custom_alias

    assert client.post("/api/v1/links", json=payload).status_code == 422


def test_rejects_url_over_2048_characters(client: TestClient) -> None:
    url = "https://example.com/" + "a" * 2029

    assert len(url) == 2049
    assert client.post("/api/v1/links", json={"url": url}).status_code == 422


def test_duplicate_custom_alias_returns_conflict(client: TestClient) -> None:
    payload = {"url": "https://example.com", "custom_alias": "same-alias"}

    assert client.post("/api/v1/links", json=payload).status_code == 201
    response = client.post("/api/v1/links", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Alias is already in use"}


def test_automatic_alias_collision_is_retried(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    occupied = {"url": "https://first.example", "custom_alias": "taken00001"}
    assert client.post("/api/v1/links", json=occupied).status_code == 201
    aliases = iter(["taken00001", "fresh00001"])
    monkeypatch.setattr("app.main.generate_alias", lambda: next(aliases))

    response = client.post("/api/v1/links", json={"url": "https://second.example"})

    assert response.status_code == 201
    assert response.json()["alias"] == "fresh00001"


def test_automatic_alias_stops_after_five_collisions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    occupied = {"url": "https://first.example", "custom_alias": "taken00001"}
    assert client.post("/api/v1/links", json=occupied).status_code == 201
    attempts = 0

    def colliding_alias() -> str:
        nonlocal attempts
        attempts += 1
        return "taken00001"

    monkeypatch.setattr("app.main.generate_alias", colliding_alias)

    response = client.post("/api/v1/links", json={"url": "https://second.example"})

    assert response.status_code == 503
    assert attempts == 5


def test_repeated_urls_create_independent_links(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    aliases = iter(["first00001", "second0001"])
    monkeypatch.setattr("app.main.generate_alias", lambda: next(aliases))
    payload = {"url": "https://example.com/repeated"}

    first = client.post("/api/v1/links", json=payload)
    second = client.post("/api/v1/links", json=payload)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["alias"] != second.json()["alias"]
