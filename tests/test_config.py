import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_database_url_is_normalized_for_psycopg(scheme: str) -> None:
    settings = Settings(database_url=f"{scheme}user:password@db.example.com:25060/app")

    assert settings.database_url == ("postgresql+psycopg://user:password@db.example.com:25060/app")


def test_psycopg_database_url_is_unchanged() -> None:
    database_url = "postgresql+psycopg://user:password@localhost/app?sslmode=require"

    assert Settings(database_url=database_url).database_url == database_url


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///tiny-url.db",
        "postgresql+psycopg://localhost",
        "not-a-url",
    ],
)
def test_non_postgresql_database_url_is_rejected(database_url: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(database_url=database_url)
