"""
API schemas for BIMOS.
"""

from typing import Any

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    output_dir: str | None = None
    meta: dict[str, Any] = {}
    results: Any | None = None

class PredictBoltzRequest(BaseModel):
    fasta_content: str
    name: str = "protein"
    num_models: int | None = None
    max_resources: bool = False
