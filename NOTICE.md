# NOTICE

## BIMOS — Biomolecular Modeling Suite

Copyright (C) 2025 Renato J. V. A.

This software is distributed under the GNU General Public License v3.0.
See [LICENSE](./LICENSE) for the full license text.

---

## How Third-Party Software Relates to BIMOS

BIMOS itself never links third-party scientific code: every computational
engine runs as a **separate process** inside the container image (or, for QM,
as a host binary the user installed). BIMOS only orchestrates these programs
via command lines and files. This process boundary is what keeps the GPLv3
licensing of BIMOS compatible with the licenses below.

| Component | License | Shipped? |
|-----------|---------|----------|
| PyQt6 / Qt6 | GPLv3 | Yes, GUI runtime |
| GROMACS 2025.4 | GPL-2.0-or-later | Yes, in the container image |
| AutoDock Vina 1.2.5 | Apache-2.0 | Yes, in the container image |
| Boltz (code + weights) | MIT | Yes, installed in the image (weights cached at runtime) |
| Meeko 0.8.0 (pinned) | LGPL-2.1 | Yes, in the container image |
| RDKit | BSD-3-Clause | Yes, in the container image |
| PyTorch (CUDA) | BSD-style | Yes, in the container image |
| FFTW3 (`libfftw3-*`) | GPL-2.0-or-later | Yes, system library in the image |
| MPI runtimes (MPICH) | Permissive (MPICH license) | Yes, system library in the image |
| NVIDIA CUDA base image | NVIDIA EULA | Yes, image base (accept the EULA when running `bimos setup`) |
| Ubuntu 24.04 | GPL / various | Yes, image base |
| OpenBabel (`obabel`) | GPL-2.0 | **No** — host prerequisite for QM, install separately |
| ORCA | Commercial / academic | **No** — never distributed; user-licensed (see below) |
| Gaussian 16 | Commercial | **No** — never distributed; user-licensed (see below) |

### Python, GUI and build dependencies

| Component | License |
|-----------|---------|
| Python | PSF-2.0 |
| Click | BSD-3-Clause |
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| python-multipart | Apache-2.0 |
| Pydantic | MIT |
| python-dotenv | BSD-3-Clause |
| PyYAML | MIT |
| rich-click | MIT |
| SQLAlchemy | MIT |
| psycopg | LGPL-3.0 |
| pywebview | BSD-3-Clause |
| QtPy | MIT |
| psutil | BSD-3-Clause |
| zstandard | BSD-3-Clause |
| Nuitka | Apache-2.0 |
| pytest | MIT |
| ruff | MIT |
| mypy | MIT |
| httpx | BSD-3-Clause |
| NumPy | BSD-3-Clause |
| SciPy | BSD-3-Clause |
| pandas | BSD-3-Clause |
| scikit-learn | BSD-3-Clause |
| Matplotlib | PSF-based |
| Pillow | HPND |

All distributed Python and GUI dependencies are open source or permissive and
compatible with GPLv3. The NVIDIA CUDA base image remains under its EULA and is
not relicensed.

---

## Proprietary QM Tools: ORCA & Gaussian 16 (NOT Distributed)

**BIMOS does not provide, distribute, copy, or grant licenses for ORCA or
Gaussian 16.** These are proprietary programs of their respective vendors:

- **ORCA** — Max Planck Institute / FACCTs. Academic and commercial licenses
  at https://www.orcasoftware.de and https://www.faccts.de.
- **Gaussian 16** — Gaussian, Inc. Licenses at https://gaussian.com.

What BIMOS does is purely **automation of tools you already licensed**: it
writes input files, launches the binary found at `ORCA_PATH` /
`GAUSSIAN_PATH` on your host, parses the text output, and copies the
resulting charges into your `.itp` files. This is lawful use of software
you licensed — BIMOS grants no rights over these programs, claims no
affiliation with their vendors, and cannot be used as a substitute for a
license. **You** are responsible for complying with the vendors' license
terms (including any restrictions on parallel runs, which is why `-j`
exists for you to stay within your entitlement).

---

## GROMACS — GPL-2.0-or-later (Bundled)

Copyright (c) 2024, GROMACS contributors.

```
GROMACS is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

GROMACS is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
```

GROMACS is distributed **inside the container image** built by
`bimos setup` (compiled from source; "or later version" makes it
compatible with BIMOS's GPLv3). It runs as a separate process; BIMOS
does not link against it.

Source: https://www.gromacs.org / https://ftp.gromacs.org/gromacs/gromacs-2025.4.tar.gz

---

## AutoDock Vina — Apache-2.0 (Bundled)

Copyright (c) 2024, The Scripps Research Institute.

```
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

Source: https://github.com/ccsb-scripps/AutoDock-Vina

---

## Boltz — MIT (Bundled; Code and Weights)

Copyright (c) 2024, Boltz authors (Jeremy Wohlwend et al.).

The Boltz repository states: *"All the code and weights are provided
under MIT license, making them freely available for both academic and
commercial uses."*

```
Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

Source: https://github.com/jwohlwend/boltz

The image installs the **PyPI package** `boltz==2.2.1`, pinned via the
`BOLTZ_VERSION` build argument in `backend/dockers/Dockerfile.bimos`. Model
weights are downloaded at runtime from the Boltz model gateway and the
`boltz-community/boltz-2` repository; both are covered by the same MIT license
and are not redistributed inside the image.

Boltz 2.2.1 also installs `cuequivariance` (Apache-2.0) when the optional
fused kernels are enabled at build time with
`--build-arg INSTALL_BOLTZ_KERNELS=ON`. It is off by default because
`boltz.yaml` ships `no_kernels: true`.

Note: Boltz predictions optionally use an external MSA server
(`use_msa_server`), which transmits your input sequence off-machine (see
[PRIVACY.md](./PRIVACY.md)). Citing ColabFold (Mirdita et al., 2022) is
required when using automatic MSA generation.

---

## Meeko — LGPL-2.1 (Bundled, Pinned)

Copyright (c) ForliLab (The Scripps Research Institute).

Meeko is licensed under the **GNU Lesser General Public License v2.1**.
The image installs the **PyPI wheel** `meeko==0.8.0`, pinned via the
`MEEKO_VERSION` build argument in `backend/dockers/Dockerfile.bimos`.

Source: https://github.com/forlilab/Meeko (the corresponding source is
available at the pinned tag `v0.8.0`; full LGPL-2.1 text ships with that
source).

Compliance notes for redistributors of the BIMOS image:

- This NOTICE names the Library and its license (prominent notice).
- The complete corresponding source is available at the pinned tag above
  (equivalent access to the distributed object code, LGPL-2.1 §4/§6).
- BIMOS uses Meeko exclusively as a **separate program**
  (`mk_prepare_ligand.py` invoked as a subprocess); it is not linked
  into BIMOS code.

---

## RDKit — BSD-3-Clause (Bundled)

Copyright (c) 2024, RDKit contributors.

```
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.
```

Source: https://github.com/rdkit/rdkit

---

## PyTorch — BSD-style (Bundled)

Copyright (c) 2016-2024, The PyTorch contributors.

```
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.
```

Source: https://github.com/pytorch/pytorch

---

## FFTW3 — GPL-2.0-or-later (Bundled System Library)

Copyright (c) 2003-2024, Matteo Frigo and Steven G. Johnson.

`libfftw3-single3` / `libfftw3-double3` ship in the image as GROMACS
dependencies, under the GNU General Public License (v2 or later).

Source: https://www.fftw.org

---

## NVIDIA CUDA — EULA (Image Base)

The Docker image built by `bimos setup` is based on NVIDIA's CUDA images.
By using `bimos setup`, you accept the NVIDIA CUDA EULA:

https://docs.nvidia.com/cuda/eula/index.html

---

## Ubuntu — GNU GPL / Various (Image Base)

The Docker image is based on Ubuntu 24.04, which includes software
licensed under the GNU GPL and other open-source licenses.
See https://ubuntu.com/legal for details.
