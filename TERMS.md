# Terms and Conditions — BIMOS

**Biomolecular Modeling Suite**, version 0.1.0 (beta).
Last updated: 2026-09-29.

By installing or running BIMOS you agree to these terms. If you do not
agree, do not use the software.

## 1. License

BIMOS itself is free software distributed under the **GNU General Public
License v3.0** ([LICENSE](./LICENSE)). You may use, study, modify, and
redistribute it under those terms. Third-party components bundled in the
container image keep their own licenses — see [NOTICE.md](./NOTICE.md).

## 2. No Warranty

BIMOS is provided **"as is"**, without warranty of any kind, express or
implied, including merchantability, fitness for a particular purpose, and
non-infringement. Scientific results (structures, scores, charges,
trajectories) must be validated by qualified judgment before any
real-world decision. The authors are not liable for results,
interpretations, data loss, or any damages arising from use.

## 3. Third-Party Software Compliance (Your Responsibility)

- **Bundled open-source tools** (GROMACS, Vina, Boltz, Meeko, RDKit,
  PyTorch, system libraries) are distributed in the image under their
  licenses ([NOTICE.md](./NOTICE.md)). Comply with each license when you
  redistribute the image or its outputs.
- **ORCA and Gaussian 16 are never distributed with BIMOS.** You must hold
  a valid license from the vendor **before** running `qm-orca` / `qm-g16`.
  BIMOS only automates tools you already licensed; it grants no rights
  over them and is not affiliated with their vendors.
- **Stay within your entitlements**: configure parallelism (`-j`) and usage
  within what your QM licenses allow. License violations are yours alone.

## 4. Acceptable Use

Do not use BIMOS to infringe third-party licenses, to circumvent license
controls of any software, or for unlawful purposes. Container images you
build or redistribute remain subject to the bundled components' licenses
(notably GPL-2.0-or-later for GROMACS/FFTW and LGPL-2.1 for Meeko).

## 5. Citation

If BIMOS contributes to published work, cite it (see
[README.md](./README.md#citation)) and cite the individual engines you used
(GROMACS, Vina, Boltz, ORCA, Gaussian, ColabFold, …) per their guidelines.

## 6. Changes

These terms may evolve with new releases; continued use after an update
constitutes acceptance. Material changes are noted in
[CHANGELOG.md](./CHANGELOG.md).
