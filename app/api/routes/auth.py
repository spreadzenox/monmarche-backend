"""Browser session authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import get_settings
from app.schemas.auth import AuthStatusResponse, LoginRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


@router.post("/login", response_model=AuthStatusResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthStatusResponse:
    auth = AuthService(db)
    if not auth.verify_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects.",
        )

    token = auth.create_session(payload.username)
    _set_session_cookie(response, token)
    return AuthStatusResponse(authenticated=True, username=payload.username)


@router.post("/logout", response_model=AuthStatusResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthStatusResponse:
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        AuthService(db).revoke_session(token)
    _clear_session_cookie(response)
    return AuthStatusResponse(authenticated=False, username=None)


@router.get("/me", response_model=AuthStatusResponse)
def auth_status(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthStatusResponse:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        return AuthStatusResponse(authenticated=False, username=None)

    username = AuthService(db).validate_session(token)
    if username is None:
        return AuthStatusResponse(authenticated=False, username=None)

    return AuthStatusResponse(authenticated=True, username=username)
