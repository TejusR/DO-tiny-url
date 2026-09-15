from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, TypeAdapter, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DEFAULT_DATABASE_URL = "postgresql+psycopg://tiny_url:tiny_url@localhost:5432/tiny_url"
HttpUrlValidator = TypeAdapter(AnyHttpUrl)


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
    public_base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    _normalize_database_url = field_validator("database_url", mode="before")(normalize_database_url)

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            value != value.strip()
            or any(character.isspace() for character in value)
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("PUBLIC_BASE_URL must be an absolute HTTP(S) URL without credentials")
        HttpUrlValidator.validate_python(normalized)
        return normalized

    @model_validator(mode="after")
    def require_production_public_base_url(self) -> "Settings":
        if self.environment == "production" and self.public_base_url == "http://localhost:8000":
            raise ValueError("PUBLIC_BASE_URL must be configured in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
