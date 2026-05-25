"""Authentication helpers."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import get_settings
from app.services.auth_service import AuthService


def require_session(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    """Require a valid browser session cookie."""
    settings = get_settings()
    if not settings.auth_enabled:
        return "anonymous"

    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Connexion requise.",
        )

    username = AuthService(db).validate_session(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée.",
        )

    return username
