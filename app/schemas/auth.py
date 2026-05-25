"""Auth request/response schemas."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AuthStatusResponse(BaseModel):
    authenticated: bool
    username: str | None = None
