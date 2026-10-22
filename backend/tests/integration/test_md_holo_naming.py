"""Holo naming: candidate (filename) names the output, internal (UNK/LIG) drives GROMACS."""

from pathlib import Path

from bimos.molecular_dynamics.pipeline import MolecularDynamicsPipeline


def _gro_text(resname: str, n: int = 2) -> str:
    atoms = "".join(
        f"{i + 1:>5d}{resname:<5s}{'C' + str(i):<5s}{i + 1:>5d}   1.000   1.000   1.000\n"
        for i in range(n)
    )
    return f"TITLE\n{n}\n{atoms}   5.000   5.000   5.000\n"


def _itp_text(mol: str, res: str, n: int = 2) -> str:
    atoms = "".join(
        f"     {i + 1}   opls_800      1    {res}   C{i:<3}  1     0.1000     12.0110\n"
        for i in range(n)
    )
    return f"[ moleculetype ]\n; Name  nrexcl\n{mol}   3\n[ atoms ]\n{atoms}\n"


def _fake_gmx(self, args: list[str], cwd, stdin: str = "") -> int:
    """Emulate file outputs of the PREP stage (no real GROMACS)."""
    from pathlib import Path as _Path

    cwd = _Path(cwd)
    opts = {args[i]: args[i + 1] for i in range(len(args) - 1) if args[i].startswith("-")}
    if args[0] == "mdrun" and "-g" in opts:
        (cwd / opts["-g"]).write_text("Converged to Fmax!\n")
    for flag in ("-o", "-p"):
        if flag in opts:
            dest = cwd / opts[flag]
            if dest.suffix == ".gro":
                dest.write_text(
                    "FAKE\n2\n"
                    f"{1:>5d}{'MET':<5s}{'CA':<5s}{1:>5d}   1.000   1.000   1.000\n"
                    f"{2:>5d}{'MET':<5s}{'CB':<5s}{2:>5d}   2.000   2.000   2.000\n"
                    "   5.000   5.000   5.000\n"
                )
            elif dest.suffix == ".top":
                dest.write_text(
                    '#include "oplsaa.ff/forcefield.itp"\n\n'
                    "[ system ]\nFake\n\n"
                    "[ molecules ]\nProtein 1\n"
                    "; Include water topology\n"
                )
            elif dest.suffix == ".pdb" and "-f" in opts and (cwd / opts["-f"]).exists():
                dest.write_text((cwd / opts["-f"]).read_text(errors="replace"))
            else:
                dest.touch()
    return 0


def _mock_gmx(monkeypatch) -> None:
    monkeypatch.setattr(MolecularDynamicsPipeline, "_gmx", _fake_gmx)


def _pdb(path: Path) -> None:
    path.write_text(
        "ATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n"
        "ATOM      2  CA  MET A   1      13.695   9.565   8.214  1.00  0.00           C\n"
        "END\n"
    )


def test_holo_run_preserves_candidate_naming(tmp_path: Path, monkeypatch) -> None:
    _mock_gmx(monkeypatch)
    pdb = tmp_path / "3HTB.pdb"
    gro = tmp_path / "JZ4.gro"
    itp = tmp_path / "JZ4.itp"
    _pdb(pdb)
    gro.write_text(_gro_text("UNK"))
    itp.write_text(_itp_text("UNK", "UNK"))

    out = tmp_path / "out"
    pipeline = MolecularDynamicsPipeline(output_dir=str(out))
    result = pipeline.run(pdb_path=str(pdb), ligand_gro=str(gro), ligand_itp=str(itp))

    assert result["comp"] == "Holo-3HTB-JZ4"
    assert result["candidate"] == "JZ4"
    assert result["ligand_internal"] == "UNK"
    cwd = Path(result["output_dir"])
    assert cwd.name == "Holo-3HTB-JZ4"
    assert (cwd / "JZ4.gro").exists()
    assert (cwd / "JZ4.itp").exists()
    assert not (cwd / "ligand.gro").exists()
    assert not (cwd / "ligand.itp").exists()


def test_holo_run_normalizes_mismatched_gro(tmp_path: Path, monkeypatch) -> None:
    _mock_gmx(monkeypatch)
    pdb = tmp_path / "3HTB.pdb"
    gro = tmp_path / "JZ4.gro"
    itp = tmp_path / "JZ4.itp"
    _pdb(pdb)
    gro.write_text(_gro_text("UNK"))
    itp.write_text(_itp_text("LIG", "LIG"))

    out = tmp_path / "out"
    pipeline = MolecularDynamicsPipeline(output_dir=str(out))
    result = pipeline.run(pdb_path=str(pdb), ligand_gro=str(gro), ligand_itp=str(itp))

    assert result["ligand_internal"] == "LIG"
    content = (Path(result["output_dir"]) / "JZ4.gro").read_text().splitlines()
    assert content[2][5:10].strip() == "LIG"


def test_run_batch_pairs_protein_x_ligand(tmp_path: Path, monkeypatch) -> None:
    _mock_gmx(monkeypatch)
    prot_dir = tmp_path / "proteins"
    lig_dir = tmp_path / "ligands"
    prot_dir.mkdir()
    lig_dir.mkdir()
    for prot in ("1AKI", "3HTB"):
        _pdb(prot_dir / f"{prot}.pdb")
    for lig in ("L1", "L2"):
        (lig_dir / f"{lig}.gro").write_text(_gro_text("UNK"))
        (lig_dir / f"{lig}.itp").write_text(_itp_text("UNK", "UNK"))
    (lig_dir / "orphan.gro").write_text(_gro_text("UNK"))

    out = tmp_path / "out"
    pipeline = MolecularDynamicsPipeline(output_dir=str(out))
    results = pipeline.run_batch(protein_dir=prot_dir, ligand_dir=lig_dir)

    comps = sorted(r["comp"] for r in results)
    assert comps == ["Holo-1AKI-L1", "Holo-1AKI-L2", "Holo-3HTB-L1", "Holo-3HTB-L2"]
    assert (out / "Analysis_graphs-Holo").is_dir()


def test_build_complex_exact_column_match(tmp_path: Path) -> None:
    prot = tmp_path / "prot.gro"
    lig = tmp_path / "JZ4.gro"
    out_gro = tmp_path / "complex.gro"
    prot.write_text(
        "PROT\n1\n"
        f"{1:>5d}{'MET':<5s}{'CA':<5s}{1:>5d}   1.000   1.000   1.000\n"
        "   5.000   5.000   5.000\n"
    )
    lig.write_text(
        "TITLE\n3\n"
        f"{1:>5d}{'UNK':<5s}{'C1':<5s}{1:>5d}   1.000   1.000   1.000\n"
        f"{2:>5d}{'UNKY':<5s}{'C2':<5s}{2:>5d}   2.000   2.000   2.000\n"
        f"{3:>5d}{'UNK':<5s}{'C3':<5s}{3:>5d}   3.000   3.000   3.000\n"
        "   5.000   5.000   5.000\n"
    )
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path / "o"))
    pipeline._build_complex(prot, lig, "UNK", out_gro)
    lines = out_gro.read_text().splitlines()
    assert lines[1].strip() == "3"
    assert sum("UNKY" in line for line in lines) == 0


def test_detect_resname_scans_all_lines(tmp_path: Path) -> None:
    gro = tmp_path / "mol.gro"
    gro.write_text(_gro_text("LIGAN", n=3))
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path / "o"))
    assert pipeline._detect_resname(gro) == "LIGAN"
