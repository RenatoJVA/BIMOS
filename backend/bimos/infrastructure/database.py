"""
Ligand database for BIMOS.

Uses SQLAlchemy + PostgreSQL.
Provides: init_db, seed_ligands, search_ligands
"""

import hashlib
import logging
import random
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Index,
    Integer,
    String,
    create_engine,
    or_,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from bimos.config.settings import settings

logger = logging.getLogger("bimos.database")

if not settings.database_url.strip():
    raise RuntimeError(
        "BIMOS_DATABASE_URL is not configured. Set it in ~/.bimos/.env before "
        "using the ligand database, e.g. "
        "postgresql+psycopg://bimos:<credential>@localhost/bimos"
    )

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class Ligand(Base):
    __tablename__ = "ligands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False, index=True)
    cid = Column(String(64), unique=True, nullable=False, index=True)
    smiles = Column(String(2048), nullable=True, index=True)
    logp = Column(Float, nullable=True)
    molar_mass = Column(Float, nullable=True)
    source = Column(String(128), nullable=True, index=True)
    active = Column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )

    __table_args__ = (
        Index("ix_ligands_logp_mw", "logp", "molar_mass"),
        Index(
            "ix_ligands_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_ligands_cid_trgm",
            "cid",
            postgresql_using="gin",
            postgresql_ops={"cid": "gin_trgm_ops"},
        ),
        Index(
            "ix_ligands_smiles_trgm",
            "smiles",
            postgresql_using="gin",
            postgresql_ops={"smiles": "gin_trgm_ops"},
        ),
    )


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    role = Column(String(16), nullable=False, default="viewer", index=True)
    active = Column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )
    created_at = Column(String(32), nullable=False)


# ── Public API ────────────────────────────────────────────────────────────────


def init_db() -> None:
    """Create all tables if they do not exist."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE ligands ADD COLUMN IF NOT EXISTS "
                    "active BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_ligands_active "
                    "ON ligands (active)"
                )
            )
    logger.info("Database schema initialized.")


def seed_ligands() -> int:
    """
    Seed the database with 1050 ligands (300 regional phytocompounds + 750 standard).
    Skips rows that already exist (CID unique constraint).
    Returns the number of rows inserted.
    """
    db: Session = SessionLocal()
    inserted = 0
    try:
        existing_cids: set[str] = set(db.scalars(select(Ligand.cid)).all())

        batch: list[Ligand] = []

        # 300 regional phytocompounds
        _phyto_smiles = [
            "OC1=CC=C(C=C1)C2OC3=CC(O)=CC(O)=C3C(=O)C2O",  # Quercetin skeleton
            "OC1=CC=C(C=C1)/C=C/C(O)=O",  # Caffeic acid
            "COC1=C(O)C=CC(=CC=O)C1",  # Sinapaldehyde variant
            "OC1=CC2=C(C=C1)OCC2",  # Benzofuranone
            "OC(=O)C1=CC=C(O)C=C1",  # 4-Hydroxybenzoic acid
        ]
        for i in range(300):
            cid = f"REG_{2000 + i}"
            if cid in existing_cids:
                continue
            batch.append(
                Ligand(
                    name=f"Phytocompound_{i + 1}",
                    cid=cid,
                    smiles=_phyto_smiles[i % len(_phyto_smiles)],
                    logp=round(random.uniform(-0.5, 4.5), 2),
                    molar_mass=round(random.uniform(150, 500), 2),
                    source="regional_phytocompound",
                )
            )

        # 750 standard compounds
        _std_smiles = [
            "CC(=O)OC1=CC=CC=C1C(=O)O",  # Aspirin
            "CC12CCC3C(C1CCC2O)CCC4=CC(=O)CCC34C",  # Testosterone skeleton
            "OC(=O)CC(O)(CC(=O)O)C(=O)O",  # Citric acid
            "NC1=NC=NC2=C1N=CN2",  # Adenine
            "OC1=NC(=O)C=CC1=O",  # Orotic acid
        ]
        for i in range(750):
            cid = f"CID_{10000 + i}"
            if cid in existing_cids:
                continue
            batch.append(
                Ligand(
                    name=f"Compound_{i + 301}",
                    cid=cid,
                    smiles=_std_smiles[i % len(_std_smiles)],
                    logp=round(random.uniform(-2.0, 7.0), 2),
                    molar_mass=round(random.uniform(100, 800), 2),
                    source="standard_db",
                )
            )

        if batch:
            db.bulk_save_objects(batch)
            db.commit()
            inserted = len(batch)
            logger.info("Inserted %d ligands.", inserted)
        else:
            logger.info("No new ligands to insert (database already seeded).")

    except Exception as exc:
        db.rollback()
        logger.error("Seeding failed: %s", exc)
        raise
    finally:
        db.close()

    return inserted


@dataclass(frozen=True)
class PropertyBounds:
    """Molar-mass / LogP bounds (the only property columns in this schema)."""

    min_mw: float | None = None
    max_mw: float | None = None
    min_logp: float | None = None
    max_logp: float | None = None


def _filtered_query(
    db: Session,
    query: str,
    source: str | None = None,
    bounds: PropertyBounds | None = None,
):  # type: ignore[no-untyped-def]
    """Base ligand query with text search plus molar-mass/LogP bounds."""
    bounds = bounds or PropertyBounds()
    q = db.query(Ligand).filter(
        Ligand.active.is_(True),
        or_(
            Ligand.name.ilike(f"%{query}%"),
            Ligand.cid.ilike(f"%{query}%"),
            Ligand.smiles.ilike(f"%{query}%"),
        ),
    )
    if source:
        q = q.filter(Ligand.source == source)
    if bounds.min_mw is not None:
        q = q.filter(Ligand.molar_mass >= bounds.min_mw)
    if bounds.max_mw is not None:
        q = q.filter(Ligand.molar_mass <= bounds.max_mw)
    if bounds.min_logp is not None:
        q = q.filter(Ligand.logp >= bounds.min_logp)
    if bounds.max_logp is not None:
        q = q.filter(Ligand.logp <= bounds.max_logp)
    return q


def search_ligands(
    query: str,
    source: str | None = None,
    limit: int = 50,
    bounds: PropertyBounds | None = None,
) -> list[Ligand]:
    """
    Search ligands by name, CID, or SMILES substring.
    Optionally filter by source, molar mass, and LogP.

    Args:
        query: Substring to match.
        source: Filter by source (e.g. 'regional_phytocompound').
        limit: Maximum rows to return.
        bounds: Molar-mass / LogP bounds.
    """
    db: Session = SessionLocal()
    try:
        q = _filtered_query(db, query, source, bounds)
        return q.limit(limit).all()
    finally:
        db.close()


def count_ligands(
    query: str,
    source: str | None = None,
    bounds: PropertyBounds | None = None,
) -> int:
    """Total matches for a text query plus molar-mass/LogP bounds."""
    db: Session = SessionLocal()
    try:
        q = _filtered_query(db, query, source, bounds)
        return q.count()
    finally:
        db.close()


def list_ligands(
    query: str = "",
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
    bounds: PropertyBounds | None = None,
) -> list[Ligand]:
    """List active ligands with text/property filters and pagination."""
    db: Session = SessionLocal()
    try:
        q = _filtered_query(db, query, source, bounds)
        return q.order_by(Ligand.name, Ligand.cid).offset(offset).limit(limit).all()
    finally:
        db.close()


def get_ligand(cid: str, include_inactive: bool = False) -> Ligand | None:
    """Return one ligand by CID, hiding soft-deleted rows by default."""
    db: Session = SessionLocal()
    try:
        q = db.query(Ligand).filter(Ligand.cid == cid)
        if not include_inactive:
            q = q.filter(Ligand.active.is_(True))
        return q.one_or_none()
    finally:
        db.close()


def create_ligand(fields: dict[str, object]) -> Ligand:
    """Insert a ligand from validated fields and return the persisted row."""
    db: Session = SessionLocal()
    try:
        ligand = Ligand(active=True, **fields)
        db.add(ligand)
        db.commit()
        db.refresh(ligand)
        return ligand
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_ligand(cid: str, **fields: object) -> Ligand | None:
    """Update editable fields of an active ligand; CID is immutable."""
    allowed = {"name", "smiles", "logp", "molar_mass", "source"}
    db: Session = SessionLocal()
    try:
        ligand = (
            db.query(Ligand)
            .filter(Ligand.cid == cid, Ligand.active.is_(True))
            .one_or_none()
        )
        if ligand is None:
            return None
        for key, value in fields.items():
            if key in allowed:
                setattr(ligand, key, value)
        db.commit()
        db.refresh(ligand)
        return ligand
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def deactivate_ligand(cid: str) -> bool:
    """Soft-delete an active ligand. Returns False when it does not exist."""
    db: Session = SessionLocal()
    try:
        ligand = (
            db.query(Ligand)
            .filter(Ligand.cid == cid, Ligand.active.is_(True))
            .one_or_none()
        )
        if ligand is None:
            return False
        ligand.active = False
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_api_token(name: str, role: str) -> tuple[str, ApiToken]:
    """Create a named API token, storing only its SHA-256 hash."""
    raw = f"bimos_{secrets.token_urlsafe(32)}"
    db: Session = SessionLocal()
    try:
        row = ApiToken(
            name=name,
            token_hash=_token_hash(raw),
            role=role,
            active=True,
            created_at=datetime.now(UTC).isoformat(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return raw, row
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_api_tokens() -> list[ApiToken]:
    db: Session = SessionLocal()
    try:
        return (
            db.query(ApiToken)
            .filter(ApiToken.active.is_(True))
            .order_by(ApiToken.id)
            .all()
        )
    finally:
        db.close()


def revoke_api_token(token_id: int) -> bool:
    db: Session = SessionLocal()
    try:
        row = (
            db.query(ApiToken)
            .filter(ApiToken.id == token_id, ApiToken.active.is_(True))
            .one_or_none()
        )
        if row is None:
            return False
        row.active = False
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def token_role(token: str) -> str | None:
    """Return the role for an active DB token, or None."""
    db: Session = SessionLocal()
    try:
        row = (
            db.query(ApiToken)
            .filter(
                ApiToken.token_hash == _token_hash(token),
                ApiToken.active.is_(True),
            )
            .one_or_none()
        )
        return row.role if row else None
    finally:
        db.close()


def has_active_api_tokens() -> bool:
    db: Session = SessionLocal()
    try:
        return db.query(ApiToken.id).filter(ApiToken.active.is_(True)).first() is not None
    finally:
        db.close()


def get_db():  # type: ignore[no-untyped-def]
    """FastAPI dependency: yields a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
