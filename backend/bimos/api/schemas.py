"""
API schemas for BIMOS.
"""

from typing import Optional, Any
from pydantic import BaseModel

class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    output_dir: Optional[str] = None
    meta: dict[str, Any] = {}
    results: Optional[Any] = None

class PredictRequest(BaseModel):
    fasta_content: str
    name: str = "protein"
    num_recycles: int | None = None
    max_resources: bool = False

class PredictBoltzRequest(BaseModel):
    fasta_content: str
    name: str = "protein"
    num_models: int | None = None
    max_resources: bool = False

class DockRequest(BaseModel):
    times: int = 1
    exhaustiveness: int = 8
    num_modes: int = 9
    margin: float = 1.0
    cpu_per_job: int = 4

class SimulateRequest(BaseModel):
    pass

class QMRequest(BaseModel):
    orca_input: str
