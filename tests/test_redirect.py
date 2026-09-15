from collections.abc import Iterator
from datetime import datetime

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
    application = create_app(Settings(public_base_url="https://short.example"))

    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    with TestClient(application) as test_client:
        yield test_client
    engine.dispose()


def create_link(client: TestClient, destination: str, alias: str = "example-link") -> None:
    response = client.post(
        "/api/v1/links",
        json={"url": destination, "custom_alias": alias},
    )
    assert response.status_code == 201


def test_redirects_to_exact_stored_url_without_caching(client: TestClient) -> None:
    destination = "https://example.com/a/path?first=one&second=two#section"
    create_link(client, destination)

    response = client.get("/example-link", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == destination
    assert response.headers["cache-control"] == "no-store"


def test_unknown_alias_returns_not_found(client: TestClient) -> None:
    response = client.get("/does-not-exist", follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == {"detail": "Short link not found"}


def test_repeated_redirects_increment_count_and_update_timestamp(client: TestClient) -> None:
    create_link(client, "https://example.com")
    created = client.get("/api/v1/links/example-link").json()
    assert created["click_count"] == 0
    assert created["last_accessed_at"] is None

    first_redirect = client.get("/example-link", follow_redirects=False)
    first_metadata = client.get("/api/v1/links/example-link").json()

    assert first_redirect.status_code == 307
    assert first_metadata["click_count"] == 1
    assert first_metadata["last_accessed_at"] is not None

    second_redirect = client.get("/example-link", follow_redirects=False)
    second_metadata = client.get("/api/v1/links/example-link").json()

    assert second_redirect.status_code == 307
    assert second_metadata["click_count"] == 2
    assert datetime.fromisoformat(second_metadata["last_accessed_at"]) >= datetime.fromisoformat(
        first_metadata["last_accessed_at"]
    )


@pytest.mark.parametrize(
    "path",
    ["/health", "/ready", "/api/v1/links/example-link"],
)
def test_named_routes_take_precedence_over_redirect_route(client: TestClient, path: str) -> None:
    if path.endswith("example-link"):
        create_link(client, "https://example.com")

    response = client.get(path, follow_redirects=False)

    assert response.status_code == 200
    assert "location" not in response.headers
