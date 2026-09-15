import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.aliases import generate_alias
from app.config import Settings, get_settings
from app.database import create_database_engine, create_session_factory, get_session
from app.models import ShortLink
from app.schemas import ShortLinkCreate, ShortLinkResponse

logger = logging.getLogger(__name__)
MAX_ALIAS_ATTEMPTS = 5


def _response_for(link: ShortLink, public_base_url: str) -> ShortLinkResponse:
    return ShortLinkResponse(
        id=link.id,
        alias=link.alias,
        original_url=link.original_url,
        short_url=f"{public_base_url}/{link.alias}",
        is_custom=link.is_custom,
        created_at=link.created_at,
        click_count=link.click_count,
        last_accessed_at=link.last_accessed_at,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    application = FastAPI(title=resolved_settings.app_name)
    application.state.database_engine = create_database_engine(resolved_settings)
    application.state.session_factory = create_session_factory(application.state.database_engine)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready")
    def ready(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("Database readiness check failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable",
            ) from None

        return {"status": "ok"}

    @application.post(
        "/api/v1/links",
        response_model=ShortLinkResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_short_link(
        payload: ShortLinkCreate,
        response: Response,
        session: Annotated[Session, Depends(get_session)],
    ) -> ShortLinkResponse:
        is_custom = payload.custom_alias is not None
        attempts = 1 if is_custom else MAX_ALIAS_ATTEMPTS

        for _ in range(attempts):
            alias = payload.custom_alias or generate_alias()
            link = ShortLink(alias=alias, original_url=payload.url, is_custom=is_custom)
            session.add(link)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                if is_custom:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Alias is already in use",
                    ) from None
                continue

            session.refresh(link)
            response.headers["Location"] = f"/api/v1/links/{link.alias}"
            return _response_for(link, resolved_settings.public_base_url)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate a unique alias",
        )

    @application.get("/api/v1/links/{alias}", response_model=ShortLinkResponse)
    def get_short_link(
        alias: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> ShortLinkResponse:
        link = session.scalar(select(ShortLink).where(ShortLink.alias == alias))
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short link not found",
            )

        return _response_for(link, resolved_settings.public_base_url)

    return application


app = create_app()
