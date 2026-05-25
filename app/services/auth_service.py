"""Session-based authentication."""

from __future__ import annotations

import hashlib
import secrets
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import UserSession


class AuthService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()

    def verify_credentials(self, username: str, password: str) -> bool:
        htpasswd_path = self._settings.auth_htpasswd_file
        if not htpasswd_path.is_file():
            return False

        result = subprocess.run(
            ["htpasswd", "-vb", str(htpasswd_path), username, password],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def create_session(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self._settings.session_max_age_seconds)
        session = UserSession(
            token_hash=self._hash_token(token),
            username=username,
            expires_at=expires_at,
        )
        self._db.add(session)
        self._db.commit()
        return token

    def validate_session(self, token: str) -> str | None:
        token_hash = self._hash_token(token)
        session = (
            self._db.query(UserSession)
            .filter(UserSession.token_hash == token_hash)
            .one_or_none()
        )
        if session is None:
            return None

        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at <= datetime.now(UTC):
            self._db.delete(session)
            self._db.commit()
            return None

        return session.username

    def revoke_session(self, token: str) -> None:
        token_hash = self._hash_token(token)
        session = (
            self._db.query(UserSession)
            .filter(UserSession.token_hash == token_hash)
            .one_or_none()
        )
        if session is not None:
            self._db.delete(session)
            self._db.commit()

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
