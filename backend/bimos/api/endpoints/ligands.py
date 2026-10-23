"""Ligand database management API for the H5 web panel."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from bimos.api.security import require_roles

router = APIRouter(prefix="/ligands", tags=["ligands"])


class LigandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    cid: str = Field(min_length=1, max_length=64)
    smiles: str | None = Field(default=None, max_length=2048)
    logp: float | None = None
    molar_mass: float | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, max_length=128)


class LigandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    smiles: str | None = Field(default=None, max_length=2048)
    logp: float | None = None
    molar_mass: float | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, max_length=128)


class LigandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cid: str
    smiles: str | None
    logp: float | None
    molar_mass: float | None
    source: str | None
    active: bool


class LigandList(BaseModel):
    items: list[LigandOut]
    total: int
    limit: int
    offset: int


class LigandFilters(BaseModel):
    q: str = ""
    source: str | None = None
    min_mw: float | None = Field(default=None, ge=0)
    max_mw: float | None = Field(default=None, ge=0)
    min_logp: float | None = None
    max_logp: float | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


@router.get("", response_model=LigandList)
def list_ligands_endpoint(
    filters: Annotated[LigandFilters, Depends()],
) -> LigandList:
    from bimos.infrastructure.database import PropertyBounds, count_ligands, list_ligands

    bounds = PropertyBounds(
        min_mw=filters.min_mw,
        max_mw=filters.max_mw,
        min_logp=filters.min_logp,
        max_logp=filters.max_logp,
    )
    total = count_ligands(filters.q, source=filters.source, bounds=bounds)
    items = list_ligands(
        filters.q,
        source=filters.source,
        limit=filters.limit,
        offset=filters.offset,
        bounds=bounds,
    )
    return LigandList(
        items=items,
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


@router.post(
    "",
    response_model=LigandOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin", "editor"))],
)
def create_ligand_endpoint(payload: LigandCreate) -> LigandOut:
    from bimos.infrastructure.database import create_ligand

    try:
        ligand = create_ligand(payload.model_dump())
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ligand CID {payload.cid!r} already exists.",
        ) from exc
    return LigandOut.model_validate(ligand)


@router.patch(
    "/{cid}",
    response_model=LigandOut,
    dependencies=[Depends(require_roles("admin", "editor"))],
)
def update_ligand_endpoint(cid: str, payload: LigandUpdate) -> LigandOut:
    from bimos.infrastructure.database import update_ligand

    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No editable fields supplied.")
    if "name" in fields and fields["name"] is None:
        raise HTTPException(status_code=400, detail="name cannot be null.")
    ligand = update_ligand(cid, **fields)
    if ligand is None:
        raise HTTPException(status_code=404, detail=f"Ligand {cid!r} not found.")
    return LigandOut.model_validate(ligand)


@router.delete(
    "/{cid}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("admin"))],
)
def deactivate_ligand_endpoint(cid: str) -> None:
    from bimos.infrastructure.database import deactivate_ligand

    if not deactivate_ligand(cid):
        raise HTTPException(status_code=404, detail=f"Ligand {cid!r} not found.")
