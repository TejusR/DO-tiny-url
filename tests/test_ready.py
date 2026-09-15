import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import get_session
from app.main import create_app


class StubSession:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.executed_sql: str | None = None

    def execute(self, statement: object) -> None:
        self.executed_sql = str(statement)
        if self.error is not None:
            raise self.error


def client_with_session(session: StubSession) -> TestClient:
    application = create_app(Settings())

    def override_session() -> Iterator[StubSession]:
        yield session

    application.dependency_overrides[get_session] = override_session
    return TestClient(application)


def test_ready_returns_ok_when_database_responds() -> None:
    session = StubSession()

    response = client_with_session(session).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert session.executed_sql == "SELECT 1"


def test_ready_returns_generic_503_and_logs_database_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = OperationalError("SELECT 1", {}, RuntimeError("database is unavailable"))
    session = StubSession(error)

    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = client_with_session(session).get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    assert "Database readiness check failed" in caplog.text
