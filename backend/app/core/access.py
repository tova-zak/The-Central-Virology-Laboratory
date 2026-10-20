"""Shared access guard for the single-team synthetic cloud demo."""
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.core.config import settings

basic = HTTPBasic(auto_error=False)


def require_access(credentials: HTTPBasicCredentials | None = Depends(basic)):
    if settings.deployment_mode == "local" and not settings.supabase_url and not settings.api_password:
        return
    valid = credentials is not None and bool(settings.api_username and settings.api_password)
    if valid:
        valid = (secrets.compare_digest(credentials.username.encode(), settings.api_username.encode())
                 and secrets.compare_digest(credentials.password.encode(), settings.api_password.encode()))
    if not valid:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Basic"})
