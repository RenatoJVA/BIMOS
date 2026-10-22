"""API security helpers: execution policy, binding guard and bearer tokens."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from bimos.config.settings import settings

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_EXECUTION_MODES = frozenset({"local", "disabled"})


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


def ensure_safe_binding(host: str) -> None:
    """Fail closed when the API is exposed without an authentication token."""
    ensure_valid_execution_mode()
    if not is_loopback(host) and not settings.api_token.strip():
        raise RuntimeError(
            f"Refusing to bind BIMOS API to {host!r} without BIMOS_API_TOKEN. "
            "Use 127.0.0.1 for local use, or set a strong token before exposing "
            "the service behind a trusted network/VPN/reverse proxy."
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


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    """Enforce ``Authorization: Bearer <BIMOS_API_TOKEN>`` when configured."""
    token = settings.api_token.strip()
    if not token:
        return
    expected = f"Bearer {token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
