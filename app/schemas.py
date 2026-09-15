import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter, field_validator

MAX_URL_LENGTH = 2048
ALIAS_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$"
RESERVED_ALIASES = frozenset({"api", "health", "ready", "docs", "redoc"})
HttpUrlValidator = TypeAdapter(AnyHttpUrl)


class ShortLinkCreate(BaseModel):
    url: Annotated[str, Field(min_length=1, max_length=MAX_URL_LENGTH)]
    custom_alias: Annotated[str | None, Field(pattern=ALIAS_PATTERN)] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if value != value.strip() or any(character.isspace() for character in value):
            raise ValueError("URL must not contain whitespace")

        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("URL must be an absolute HTTP(S) URL without credentials")

        # This also validates hosts, IPv4/IPv6 addresses, and malformed ports.
        HttpUrlValidator.validate_python(value)
        return value

    @field_validator("custom_alias")
    @classmethod
    def reject_reserved_alias(cls, value: str | None) -> str | None:
        if value in RESERVED_ALIASES:
            raise ValueError("Alias is reserved")
        return value


class ShortLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alias: str
    original_url: str
    short_url: str
    is_custom: bool
    created_at: datetime
    click_count: int
    last_accessed_at: datetime | None
