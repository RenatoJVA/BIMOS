"""
Ligand database for BIMOS.

Uses SQLAlchemy + PostgreSQL.
Provides: init_db, seed_ligands, search_ligands
"""

import logging
import random
from dataclasses import dataclass

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    String,
    create_engine,
    or_,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from bimos.config.settings import settings

logger = logging.getLogger("bimos.database")

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

    # Composite index for chemical property searches
    __table_args__ = (Index("ix_ligands_logp_mw", "logp", "molar_mass"),)


# ── Public API ────────────────────────────────────────────────────────────────


def init_db() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
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
        existing_cids: set[str] = set(db.scalars(db.query(Ligand.cid)).all())

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
        or_(
            Ligand.name.ilike(f"%{query}%"),
            Ligand.cid.ilike(f"%{query}%"),
            Ligand.smiles.ilike(f"%{query}%"),
        )
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


def get_db():  # type: ignore[no-untyped-def]
    """FastAPI dependency: yields a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
