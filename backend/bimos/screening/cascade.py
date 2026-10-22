"""End-to-end virtual screening cascade: APO -> Docking -> QM -> top-N HOLO.

The screening library lives in two forms sharing the same stem
(e.g. ``JZ4.sdf`` for docking plus ``JZ4.gro``/``JZ4.itp`` already
parametrized for MD/QM). Hits are matched by candidate stem, so no ligand
parametrization is ever generated: Meeko (pinned in the image) only
prepares PDBQT for Vina, exactly as in the standalone docking pipeline.

Progress persists in ``screen.json`` inside the output directory, so a
re-run transparently resumes after the last completed stage.
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bimos.docking import run_docking_pipeline
from bimos.molecular_dynamics import run_md_simulation
from bimos.quantum_chemistry import run_gaussian_pipeline, run_orca_pipeline
from bimos.screening.report import write_screen_report
from bimos.shared.pipeline import Pipeline

logger = logging.getLogger("bimos.screening")

STAGES = ("apo", "dock", "qm", "holo", "report", "done")
_QM_BACKENDS = ("orca", "g16")


class ScreenCascade(Pipeline):
    """APO -> Docking -> QM charge refinement -> top-N HOLO cascade."""

    workspace_subdir = "screen"

    def __init__(
        self,
        output_dir: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        qm_backend: str = "orca",
        charge: int = 0,
        max_jobs: int | None = None,
        min_score: float | None = None,
        top_n: int = 5,
        max_resources: bool | None = None,
        **dock_kwargs: Any,
    ) -> None:
        super().__init__(output_dir, on_output)
        if qm_backend not in _QM_BACKENDS:
            raise ValueError(f"Invalid qm_backend '{qm_backend}': use 'orca' or 'g16'.")
        if top_n < 1:
            raise ValueError(f"Invalid top_n {top_n}: must be >= 1.")
        self.qm_backend = qm_backend
        self.charge = charge
        self.max_jobs = max_jobs
        self.min_score = min_score
        self.top_n = top_n
        self.max_resources = max_resources
        self.dock_kwargs = dock_kwargs
        self.state_path = self.output_dir / "screen.json"

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                logger.warning("screen.json unreadable, restarting the cascade")
        return {"stage": "apo", "artifacts": {}}

    def _save_state(self, stage: str, artifacts: dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps({"stage": stage, "artifacts": artifacts}, indent=2, default=str),
            encoding="utf-8",
        )

    def run(  # type: ignore[override]
        self,
        protein: str | None = None,
        protein_eq: str | None = None,
        ligands_sdf: str | None = None,
        dataset: str | None = None,
        ligand_dir: str | None = None,
    ) -> dict[str, Any]:
        if (protein is None) == (protein_eq is None):
            raise ValueError("Provide --protein or --protein-eq (mutually exclusive).")
        if (ligands_sdf is None) == (dataset is None):
            raise ValueError("Provide a ligand SDF or --dataset (mutually exclusive).")
        if not ligand_dir:
            raise ValueError("Missing --ligand-dir with the parametrized .gro+.itp pairs.")
        lib = Path(ligand_dir)
        if not lib.is_dir():
            raise ValueError(f"--ligand-dir is not a directory: {ligand_dir}")

        state = self._load_state()
        artifacts: dict[str, Any] = state.get("artifacts", {})
        stage: str = state.get("stage", "apo")
        if stage not in STAGES:
            stage = "apo"

        receptor = str(Path(protein_eq if protein_eq is not None else protein or "").resolve())
        if stage == "apo" and protein_eq is None:
            artifacts["apo_dir"] = self._stage_apo(str(Path(protein or "").resolve()))
            stage = "dock"
            self._save_state(stage, artifacts)
        elif stage == "apo":
            self.log("APO skipped (--protein-eq provided)")
            stage = "dock"
            self._save_state(stage, artifacts)

        if stage == "dock":
            artifacts["dock_dir"], artifacts["ranking"] = self._stage_dock(receptor, ligands_sdf, dataset)
            stage = "qm"
            self._save_state(stage, artifacts)

        if stage == "qm":
            selections = self._select_top_n(artifacts["ranking"], lib)
            self._merge_stored_flags(selections, artifacts.get("selections", []))
            artifacts["selections"] = selections
            self.log(
                f"{len(selections)} hits selected x (1 QM + 1 full HOLO each). "
                "A failed hit is flagged and the run continues with the rest."
            )
            self._save_state(stage, artifacts)
            self._run_qm_stage(selections, lambda: self._save_state(stage, artifacts))
            stage = "holo"
            self._save_state(stage, artifacts)

        if stage == "holo":
            selections = self._migrated_selections(artifacts)
            artifacts["selections"] = selections
            self._run_holo_stage(receptor, selections, lambda: self._save_state(stage, artifacts))
            stage = "report"
            self._save_state(stage, artifacts)

        if stage == "report":
            artifacts["report"] = self._stage_report(artifacts)
            stage = "done"
            self._save_state(stage, artifacts)

        selections = self._migrated_selections(artifacts)
        ok = [s for s in selections if s.get("holo_ok")]
        best = selections[0]
        first_ok = ok[0] if ok else {}
        return {
            "status": "completed",
            "output_dir": str(self.output_dir),
            "candidate": best["candidate"],
            "vina_score_kcal_mol": best["score"],
            "holo_dir": first_ok.get("holo_dir", ""),
            "hirsh_itp": first_ok.get("hirsh_itp", ""),
            "candidates": [s["candidate"] for s in selections],
            "vina_scores": [s["score"] for s in selections],
            "holo_dirs": [s.get("holo_dir", "") for s in selections],
            "hirsh_itps": [s.get("hirsh_itp", "") for s in selections],
            "report": artifacts["report"],
        }

    def _stage_apo(self, protein: str) -> str:
        self.log("Screen 1/5: APO (validates stability before docking)")
        result = run_md_simulation(
            pdb_path=protein,
            output_dir=str(self.output_dir / "apo"),
            on_output=self.on_output,
            max_resources=self.max_resources,
        )
        if isinstance(result, list):  # pragma: no cover - single mode never returns a list
            raise RuntimeError("Unexpected APO stage in batch mode.")
        self.log(f"APO OK: {result['output_dir']}")
        return str(result["output_dir"])

    def _stage_dock(
        self, receptor: str, ligands_sdf: str | None, dataset: str | None
    ) -> tuple[str, list[dict[str, Any]]]:
        self.log("Screen 2/5: Docking (Meeko prepares PDBQT, Vina scores)")
        sdf = self._resolve_sdf(ligands_sdf, dataset)
        result = run_docking_pipeline(
            protein_pdb=receptor,
            ligands_sdf=sdf,
            output_dir=str(self.output_dir / "dock"),
            on_output=self.on_output,
            max_resources=self.max_resources,
            **self.dock_kwargs,
        )
        results = result.get("results", [])
        if not results:
            raise RuntimeError("Docking produced no valid poses: nothing to rank, cascade aborted.")
        ranking = sorted(results, key=lambda hit: hit["best_score_kcal_mol"])
        for pos, hit in enumerate(ranking, start=1):
            self.log(f"  #{pos} {hit['complex']}: {hit['best_score_kcal_mol']:.3f} kcal/mol")
        return str(result["output_dir"]), ranking

    def _resolve_sdf(self, ligands_sdf: str | None, dataset: str | None) -> str:
        if ligands_sdf:
            sdf = Path(ligands_sdf)
            if not sdf.exists():
                raise ValueError(f"Ligand SDF not found: {ligands_sdf}")
            return str(sdf.resolve())
        from bimos.infrastructure.chembl_db import export_to_sdf, get_available_datasets

        available = get_available_datasets()
        if dataset not in available:
            raise ValueError(f"Dataset '{dataset}' not found. Available: {', '.join(available)}")
        dest = self.output_dir / "ligands" / f"{dataset}.sdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.log(f"Exporting dataset '{dataset}'...")
        export_to_sdf(dataset or "", dest)
        return str(dest)

    def _select_top_n(self, ranking: list[dict[str, Any]], lib: Path) -> list[dict[str, Any]]:
        self.log(f"Screen 3/5: top-{self.top_n} selection by Vina energy")
        selections: list[dict[str, Any]] = []
        skipped: list[str] = []
        for pos, hit in enumerate(ranking, start=1):
            if len(selections) >= self.top_n:
                break
            score = float(hit["best_score_kcal_mol"])
            candidate = _candidate_from_complex(str(hit["complex"]))
            if self.min_score is not None and score > self.min_score:
                skipped.append(f"{candidate} (score {score:.2f} > cutoff {self.min_score})")
                continue
            gro = lib / f"{candidate}.gro"
            itp = lib / f"{candidate}.itp"
            if not gro.exists() or not itp.exists():
                skipped.append(f"{candidate} (no .gro+.itp pair in library)")
                continue
            self.log(f"Selected #{pos} {candidate} ({score:.3f} kcal/mol)")
            selections.append(
                {
                    "candidate": candidate,
                    "gro": str(gro),
                    "itp": str(itp),
                    "score": score,
                    "rank": pos,
                    "qm_ok": False,
                    "holo_ok": False,
                    "hirsh_itp": "",
                    "holo_dir": "",
                    "error": "",
                }
            )
        if len(selections) < self.top_n:
            scope = f"top-{self.top_n} requested, {len(selections)} viable"
            self.log(
                f"Warning: {scope}" + (f" (skipped: {'; '.join(skipped)})" if skipped else ""), logging.WARNING
            )
        if not selections:
            detail = "; ".join(skipped) if skipped else "empty ranking"
            raise RuntimeError(f"No viable candidate for HOLO: {detail}.")
        return selections

    @staticmethod
    def _merge_stored_flags(selections: list[dict[str, Any]], stored: list[dict[str, Any]]) -> None:
        """Restore per-hit progress flags when resuming (matched by candidate)."""
        by_candidate = {s["candidate"]: s for s in stored}
        for selection in selections:
            old = by_candidate.get(selection["candidate"])
            if old:
                selection.update(
                    {
                        k: old.get(k, selection[k])
                        for k in ("qm_ok", "holo_ok", "hirsh_itp", "holo_dir", "error")
                    }
                )

    def _migrated_selections(self, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
        """Read selections, migrating the legacy single-selection state format."""
        if "selections" in artifacts:
            return artifacts["selections"]
        old = artifacts.get("selection")
        if not old:
            raise RuntimeError("Inconsistent state: no selection (repeat from dock).")
        return [
            {
                **old,
                "rank": 1,
                "qm_ok": True,
                "holo_ok": True,
                "hirsh_itp": artifacts.get("hirsh_itp", ""),
                "holo_dir": artifacts.get("holo_dir", ""),
                "error": "",
            }
        ]

    def _run_qm_stage(self, selections: list[dict[str, Any]], save: Callable[[], None]) -> None:
        for selection in selections:
            if selection["qm_ok"] and selection["hirsh_itp"] and Path(selection["hirsh_itp"]).exists():
                self.log(f"QM {selection['candidate']}: already refined, skipped")
                continue
            try:
                selection["hirsh_itp"] = self._stage_qm(selection)
                selection["qm_ok"] = True
                selection["error"] = ""
            except Exception as exc:
                selection["qm_ok"] = False
                selection["hirsh_itp"] = ""
                selection["error"] = f"QM: {exc}"
                self.log(f"QM {selection['candidate']} failed ({exc}), continuing with the rest", logging.ERROR)
            save()
        if not any(s["qm_ok"] for s in selections):
            raise RuntimeError("QM failed for all hits: cascade aborted.")

    def _run_holo_stage(
        self, receptor: str, selections: list[dict[str, Any]], save: Callable[[], None]
    ) -> None:
        for selection in selections:
            if not selection["qm_ok"]:
                continue
            if selection["holo_ok"] and selection["holo_dir"]:
                self.log(f"HOLO {selection['candidate']}: already simulated, skipped")
                continue
            try:
                selection["holo_dir"] = self._stage_holo(
                    receptor, selection["candidate"], selection["gro"], selection["hirsh_itp"]
                )
                selection["holo_ok"] = True
                selection["error"] = ""
            except Exception as exc:
                selection["holo_ok"] = False
                selection["holo_dir"] = ""
                selection["error"] = f"HOLO: {exc}"
                self.log(f"HOLO {selection['candidate']} failed ({exc}), continuing with the rest", logging.ERROR)
            save()
        if not any(s["holo_ok"] for s in selections):
            raise RuntimeError("HOLO failed for all hits: cascade aborted.")

    def _stage_qm(self, selection: dict[str, Any]) -> str:
        candidate = selection["candidate"]
        self.log(f"Screen 4/5: QM ({self.qm_backend}) refines charges for {candidate}")
        qm_dir = self.output_dir / "qm" / candidate
        qm_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(selection["gro"], qm_dir / f"{candidate}.gro")
        shutil.copy2(selection["itp"], qm_dir / f"{candidate}.itp")
        runner = run_orca_pipeline if self.qm_backend == "orca" else run_gaussian_pipeline
        result = runner(
            str(qm_dir),
            charge=self.charge,
            max_jobs=self.max_jobs,
            on_output=self.on_output,
            max_resources=self.max_resources,
        )
        hirsh = qm_dir / f"{candidate}-hirsh.itp"
        updated = [str(p) for p in result.get("results", [])]
        if not hirsh.exists() or str(hirsh) not in updated:
            raise RuntimeError(f"QM produced no Hirshfeld charges for {candidate}: cascade aborted.")
        self.log(f"QM OK: {hirsh}")
        return str(hirsh)

    def _stage_holo(self, receptor: str, candidate: str, gro: str, hirsh_itp: str) -> str:
        self.log(f"Screen 5/5: HOLO of {candidate} with refined charges")
        result = run_md_simulation(
            pdb_path=receptor,
            ligand_gro=gro,
            ligand_itp=hirsh_itp,
            output_dir=str(self.output_dir / "holo" / candidate),
            on_output=self.on_output,
            max_resources=self.max_resources,
        )
        if isinstance(result, list):  # pragma: no cover - single mode never returns a list
            raise RuntimeError("Unexpected HOLO stage in batch mode.")
        self.log(f"HOLO OK: {result['output_dir']}")
        return str(result["output_dir"])

    def _stage_report(self, artifacts: dict[str, Any]) -> str:
        by_candidate = {s["candidate"]: s for s in self._migrated_selections(artifacts)}
        rows = []
        for pos, hit in enumerate(artifacts["ranking"], start=1):
            candidate = _candidate_from_complex(str(hit["complex"]))
            selection = by_candidate.get(candidate, {})
            rows.append(
                {
                    "rank": pos,
                    "candidate": candidate,
                    "vina_score_kcal_mol": hit["best_score_kcal_mol"],
                    "selected": candidate in by_candidate,
                    "qm_backend": self.qm_backend if candidate in by_candidate else "",
                    "hirsh_itp": selection.get("hirsh_itp", ""),
                    "holo_dir": selection.get("holo_dir", ""),
                    "holo_ok": selection.get("holo_ok", False),
                    "error": selection.get("error", ""),
                }
            )
        report = write_screen_report(self.output_dir / "screen_report.csv", rows)
        self.log(f"Report: {report}")
        return str(report)


def _candidate_from_complex(complex_name: str) -> str:
    """Extract the ligand stem from a ``<PROT>-<LIG>`` docking complex name."""
    if "-" not in complex_name:
        return complex_name
    return complex_name.split("-", 1)[1]


def run_screen(**kwargs: Any) -> dict[str, Any]:
    """Run the screening cascade with explicit keyword arguments."""
    output_dir = kwargs.pop("output_dir", None)
    on_output = kwargs.pop("on_output", None)
    run_keys = ("protein", "protein_eq", "ligands_sdf", "dataset", "ligand_dir")
    run_kwargs = {key: kwargs.pop(key, None) for key in run_keys}
    cascade = ScreenCascade(output_dir=output_dir, on_output=on_output, **kwargs)
    return cascade.run(**run_kwargs)
