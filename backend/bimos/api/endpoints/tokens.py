"""Named API token management with roles."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from bimos.api.security import Principal, require_roles

router = APIRouter(prefix="/tokens", tags=["tokens"])

Role = Literal["admin", "editor", "viewer"]
AdminOnly = Annotated[Principal, Depends(require_roles("admin"))]


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    role: Role = "viewer"


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str
    active: bool
    created_at: str


class TokenCreated(TokenOut):
    token: str


@router.get("", response_model=list[TokenOut])
def list_tokens(_: AdminOnly) -> list[TokenOut]:
    from bimos.infrastructure.database import list_api_tokens

    return [TokenOut.model_validate(row) for row in list_api_tokens()]


@router.post("", response_model=TokenCreated, status_code=status.HTTP_201_CREATED)
def create_token(payload: TokenCreate, _: AdminOnly) -> TokenCreated:
    from bimos.infrastructure.database import create_api_token

    raw, row = create_api_token(payload.name, payload.role)
    return TokenCreated(
        id=row.id,
        name=row.name,
        role=row.role,
        active=row.active,
        created_at=row.created_at,
        token=raw,
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: int, _: AdminOnly) -> None:
    from bimos.infrastructure.database import revoke_api_token

    if not revoke_api_token(token_id):
        raise HTTPException(status_code=404, detail=f"Token {token_id} not found.")
