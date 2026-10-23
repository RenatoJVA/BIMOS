"""API security helpers: execution policy, binding guard and bearer tokens."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from bimos.config.settings import settings

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_EXECUTION_MODES = frozenset({"local", "disabled"})


@dataclass(frozen=True)
class Principal:
    role: str
    source: str = "token"


def is_loopback(host: str) -> bool:
    return host.strip().lower() in LOOPBACK_HOSTS


def execution_enabled() -> bool:
    """Return whether this process is allowed to launch computational jobs."""
    return settings.execution_mode != "disabled"


def ensure_valid_execution_mode() -> str:
    mode = settings.execution_mode.strip().lower()
    if mode not in _EXECUTION_MODES:
        raise RuntimeError(
            f"Invalid BIMOS_EXECUTION_MODE={settings.execution_mode!r}; "
            "expected 'local' or 'disabled'."
        )
    return mode


def _has_active_db_tokens() -> bool:
    try:
        from bimos.infrastructure.database import has_active_api_tokens
    except RuntimeError:
        return False
    try:
        return has_active_api_tokens()
    except Exception:
        return False


def ensure_safe_binding(host: str) -> None:
    """Fail closed when the API is exposed without an authentication token."""
    ensure_valid_execution_mode()
    if is_loopback(host):
        return
    if settings.api_token.strip() or _has_active_db_tokens():
        return
    raise RuntimeError(
        f"Refusing to bind BIMOS API to {host!r} without BIMOS_API_TOKEN or an "
        "active database token. Use 127.0.0.1 for local use, or create a "
        "strong token before exposing the service behind a trusted "
        "network/VPN/reverse proxy."
    )


def require_execution() -> None:
    """Reject job submission when the deployment is API/UI-only."""
    if not execution_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Pipeline execution is disabled in this deployment. Run BIMOS "
                "on the compute host (BIMOS_EXECUTION_MODE=local)."
            ),
        )


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    prefix = "Bearer "
    return authorization[len(prefix):].strip() if authorization.startswith(prefix) else ""


def _db_token_role(token: str) -> str | None:
    try:
        from bimos.infrastructure.database import token_role
    except RuntimeError:
        return None
    try:
        return token_role(token)
    except Exception:
        return None


def require_api_token(
    authorization: str | None = Header(default=None),
) -> Principal:
    """Enforce a bearer token and return the caller role.

    ``BIMOS_API_TOKEN`` remains the bootstrap admin token. Additional named
    tokens live hashed in the database and carry ``admin``/``editor``/``viewer``
    roles. With no env token and no active DB tokens, loopback local mode is
    allowed as before.
    """
    configured = settings.api_token.strip()
    provided = _bearer_token(authorization)
    if configured and authorization and hmac.compare_digest(
        authorization, f"Bearer {configured}"
    ):
        return Principal("admin", "env")
    if provided:
        role = _db_token_role(provided)
        if role:
            return Principal(role, "db")
    if not configured and not _has_active_db_tokens():
        return Principal("admin", "local")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*allowed: str):  # type: ignore[no-untyped-def]
    """Return a dependency that requires one of *allowed* roles."""

    def _check(principal: Annotated[Principal, Depends(require_api_token)]) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{principal.role}' is not allowed for this operation.",
            )
        return principal

    return _check
