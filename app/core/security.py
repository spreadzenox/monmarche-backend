"""API authentication helpers."""

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> None:
    """Verify Bearer token when API_AUTH_TOKEN is configured."""
    settings = get_settings()
    expected_token = settings.api_auth_token

    if not expected_token:
        return

    if credentials is None or credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
