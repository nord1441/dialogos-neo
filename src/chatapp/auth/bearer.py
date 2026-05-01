from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, status

from ..config import Settings


def require_bearer(request: Request) -> None:
    settings: Settings = request.app.state.settings
    expected = settings.api_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_TOKEN is not configured on the server",
        )
    auth = request.headers.get("authorization", "")
    prefix = "Bearer "
    if not auth.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth[len(prefix):]
    if not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        )
