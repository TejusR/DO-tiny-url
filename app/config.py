from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DEFAULT_DATABASE_URL = "postgresql+psycopg://tiny_url:tiny_url@localhost:5432/tiny_url"


def normalize_database_url(value: str) -> str:
    """Return a validated PostgreSQL URL using SQLAlchemy's Psycopg 3 dialect."""
    normalized = value.strip()
    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql+psycopg://", 1)
    elif normalized.startswith("postgresql://"):
        normalized = normalized.replace("postgresql://", "postgresql+psycopg://", 1)

    try:
        url = make_url(normalized)
    except (ArgumentError, TypeError, ValueError) as exc:
        raise ValueError("DATABASE_URL must be a valid PostgreSQL URL") from exc

    if url.drivername != "postgresql+psycopg" or not url.database:
        raise ValueError("DATABASE_URL must use PostgreSQL with the Psycopg 3 driver")

    return normalized


class Settings(BaseSettings):
    app_name: str = "Tiny URL"
    environment: str = "development"
    database_url: str = DEFAULT_DATABASE_URL

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    _normalize_database_url = field_validator("database_url", mode="before")(normalize_database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
