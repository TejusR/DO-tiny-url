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


def test_returns_same_metadata_as_creation(client: TestClient) -> None:
    created = client.post(
        "/api/v1/links",
        json={"url": "https://example.com/a?q=1", "custom_alias": "example-link"},
    )

    response = client.get("/api/v1/links/example-link")

    assert response.status_code == 200
    assert response.json() == created.json()


def test_unknown_alias_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/links/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Short link not found"}
