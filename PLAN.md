# PLAN — Estabilización post-auditoría

**Base:** `7a5bbda` (2026-10-21). **Rama:** `refactor/backend_V2`.
**Regla:** no se retoma `R-ROAD-01`/`R-ROAD-02` hasta cerrar los P0.

## Arquitectura de ejecución (decisión)

- **Pixi:** solo desarrollo, tests, CI y build. No se distribuye ni lo necesita el
  usuario final.
- **BIMOS nativo:** CLI, GUI y API corren en el host (instalador Nuitka o `pip
  install`).
- **Docker/Podman:** ejecutan únicamente los motores científicos (Boltz, Vina,
  GROMACS). `bimos setup` construye `localhost/bimos/global:latest`.
- **QM:** ORCA/G16 corren en el host con la licencia del usuario.
- **API remota:** loopback por defecto; fuera de loopback exige
  `BIMOS_API_TOKEN`. TLS en reverse proxy. Acceso recomendado: túnel SSH.
- **Compose:** API/PostgreSQL opcional. No monta `docker.sock` ni se presenta como
  ejecutor de pipelines; en ese modo los endpoints de ejecución responden 503 con
  un mensaje claro. Para ejecución remota multi-usuario, el camino futuro es un
  worker agent, no el socket de Docker.

## P0 — Bloqueantes

| ID | Objetivo | Cambios | Test / aceptación | Estado |
|---|---|---|---|---|
| P0-01 | Imagen API construible | `backend/Dockerfile` copia `bimos/`; `.dockerignore` actualizado | Test estático del Dockerfile + `docker build -f backend/Dockerfile backend` | Hecho: build real con `podman` + smoke API (health 200, auth 401/200) |
| P0-02 | CI de release con `fpm` | `.github/workflows/build.yml` instala Ruby/fpm y verifica versión | Test estático del workflow + tag build produce `.deb` y `--verify` | Workflow listo y **desactivado** (solo `workflow_dispatch`) por costo/límite de CI; falta activarlo y ejecutar el tag build cuando el operador lo apruebe |
| P0-03 | API host-only | compose sin socket, bind loopback, `BIMOS_EXECUTION_MODE=disabled` en contenedor | Test de compose seguro + endpoint de ejecución 503 en modo disabled | Hecho: compose validado y smoke real del contenedor |
| P0-04 | Recursos reales | facades con `max_resources=None`; `--cpu-per-job` en dock/screen; `max_jobs` explícito en configs QM; `--jobs` respeta CLI | Tests de resolución MAX y de concurrencia QM | Hecho: además MAX acota `max_jobs` a la RAM instalada |
| P0-05 | `screen --protein-eq` | avanzar `stage` a `dock` y persistir tras omitir APO | Test de cascada completa sin APO | Hecho |
| P0-06 | MD verificable | `-g` con log real, rc de `grompp`/`mdrun`, convergencia real y detección de etapa | Tests de rc, log y reanudación | Hecho: incluye `trjcat` con rutas relativas al contenedor |
| P0-07 | Ciclo de vida | cancelar solo jobs no terminales; SSE termina y usa cursor | Tests de store y endpoint | Hecho |
| P0-08 | CLI honesta | `run_tracked` propaga fallo y registra cancelación | Tests de exit code y evento de cancelación | Hecho |
| P0-09 | Jobs aislados | directorio por `job.id`, nombre seguro, límite de upload | Tests de colisión y tamaño | Hecho |
| P0-10 | Auth/exposición | token obligatorio fuera de loopback; CORS/allowlist; compose loopback | Tests de auth y bind | Hecho |

## P1 — Alto impacto (después de P0)

1. **Hecho**: Frontend con `API_BASE` configurable (`VITE_API_BASE`, same-origin
   por defecto), tipos `screen`/`qm-g16`/`workflow-*`, `JobResults` para screen y
   QM, filtros de grid y etiquetas Boltz-2.
2. **Hecho**: `settings.py` sin side effects al importar (`initialize()` explícito
   en CLI/API) y merge profundo del perfil custom sobre los defaults empaquetados.
3. **Hecho**: driver DB unificado (`psycopg[binary]>=3.2`, URL
   `postgresql+psycopg`, lock actualizado, compose/template alineados).
4. **Hecho**: `container.py` con errores explícitos de timeout/cancelación/ausencia
   de runtime (`raise_on_error`), `LD_LIBRARY_PATH` por arquitectura y mounts
   read-only (`/scripts` en docking).
5. **Hecho**: dockers empaquetados una sola vez (`/opt/bimos/lib/dockers`),
   versión única desde `pyproject.toml` (API/CLI/frontend derivan), y
   `docs/deployment.md` con modos nativo/compose/remoto y checklist.
6. **Hecho**: P2 — test de predicción aislado de `nvidia-smi`, `build.py` lee
   solo la cabecera ELF, permisos de CI con mínimo privilegio y workflow manual
   (`workflow_dispatch`) hasta aprobar el presupuesto.

## Orden de ejecución

1. P0-01/P0-02 (build/release).
2. P0-04 (recursos).
3. P0-05/P0-06 (correctitud).
4. P0-07/P0-08 (ciclo de vida).
5. P0-03/P0-09/P0-10 (API).
6. Lint + suite completa + integración.
7. P1 y luego roadmap existente.

## Gates

- `pixi run lint` sin errores.
- `pixi run test`: 520 passed, 0 fallos (los 2 tests QM se saltan solo si el
  host tiene ORCA/G16 configurados).
- `docker build -f backend/Dockerfile backend` y `bimos --version` en la imagen.
- `docker compose config` seguro (sin `docker.sock`, puertos loopback).
- Integración 7/7 con salida real (2026-10-21, P1): APO 26s, HOLO 38s, docking
  39.7s (-7.081 kcal/mol), Boltz 3:02 con GPU (util pico 43%, VRAM pico 4.6GB),
  ORCA 13.4s y G16 23.1s actualizan 1 ITP cada uno.
- `builder.py --verify` verde; `.deb` reconstruido sin la copia duplicada
  `/opt/bimos/dockers` (dockers solo en `/opt/bimos/lib/dockers`).
- CI/CD preparado pero **sin activar**: el workflow solo corre por
  `workflow_dispatch`; el tag build real (P0-02) queda pendiente de aprobación
  por costo/límite de GitHub Actions.

## Riesgos

- El build Docker descarga torch/CUDA: validar en CI o con caché local.
- `BIMOS_EXECUTION_MODE=disabled` debe fallar antes de crear jobs, no después.
- Cambiar `max_resources` de `False` a `None` puede alterar el default del API;
  los endpoints deben seguir enviando `False` explícito.
- La compatibilidad de `psycopg` v3 requiere cambiar la URL y el extra `db`.

## Última validación (2026-10-21, cierre P1)

- `pixi run lint`: limpio.
- `pixi run test`: **520 passed, 0 failed** (2 tests QM saltables si ORCA/G16
  están configurados en el host).
- Frontend: `bun run lint` y `bun run build` verdes (`dist/` regenerado).
- Integración real `python test.py`: **7/7 PASS**, con artefactos verificados
  (MD `min-*-mdrun.log` + `trjcat`, docking `-7.081 kcal/mol`, Boltz
  `lysozyme_best.cif` con evidencia GPU util max 43% / 4564 MiB, ORCA/G16
  `Updated 1 ITP files`).
- `builder.py --skip-nuitka --skip-frontend` + `builder.py --verify`: `.deb`
  reconstruido, sin `/opt/bimos/dockers`, payload y NSS verificados.
- Build/smoke API: `podman build -f backend/Dockerfile -t bimos-api:p0-test backend`
  y health/auth probados; `docker compose config` validado.
