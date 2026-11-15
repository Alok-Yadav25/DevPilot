import hmac
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings

security = HTTPBearer(auto_error=False)


def settings_for(request: Request) -> Settings:
    return request.app.state.settings


def require_access(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> None:
    expected = request.app.state.settings.api_access_token.get_secret_value()
    if not expected:
        raise HTTPException(
            503, "Set API_ACCESS_TOKEN on the worker to enable protected endpoints."
        )
    if credentials is None or not hmac.compare_digest(credentials.credentials, expected):
        raise HTTPException(401, "Connect with the worker's access token.")


def session_for(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


DB = Annotated[Session, Depends(session_for)]
