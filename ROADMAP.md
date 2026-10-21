# ROADMAP — Trabajo futuro

## R-ROAD-01 · Builds multiplataforma (Windows y macOS) vía CI

**Estado:** Observado y postergado (2026-10-20, decisión del operador). El flujo Linux
está compilado, verificado y distribuido (backend/dist + installer/dist, SHA256SUMS).

### Conclusión de la investigación

- **xtool (github.com/xtool-org/xtool) no aplica**: es un reemplazo de Xcode para apps
  Swift/SwiftPM (iOS/macOS nativos). BIMOS es Python + Nuitka + PyQt6/QtWebEngine +
  pywebview; no hay ruta con xtool.
- **Nuitka no soporta cross-compilación** (confirmado por el autor, issue Nuitka #2149):
  cada binario se compila en su propio SO. Windows requiere MSVC 2022 o MinGW64
  (Nuitka puede descargar MinGW64 solo); macOS requiere Clang de Xcode y bundle
  `.app` (`--mode=app`; dmg con create-dmg). El binario Linux congela la glibc del
  builder — por eso el workflow usa ubuntu-24.04.
- **No se necesitan máquinas propias**: GitHub Actions compila de forma nativa en
  `windows-latest` y `macos-14` (arm64). Gratis si el repositorio es público; en repo
  privado se cobran minutos con multiplicador (Windows 2×, macOS 10×; ≈20-40 min por
  build). El `.deb` es el único target ya cubierto hoy.
- pixi soporta multiplataforma: `platforms = ["linux-64", "osx-arm64", "win-64"]` con
  features por SO (`[feature.win]`, `[feature.macos]`); Qt6, PyQt6-WebEngine y bun
  existen en conda-forge para esas plataformas; `setup-pixi` respeta `pixi.lock`
  multiplataforma (nada manual).

### Definición de hecho (cuando se retome)

1. Ampliar `backend/pixi.toml` a las 3 plataformas con features por SO.
2. Reactivar en `.github/workflows/build.yml` los jobs `build-windows` (NSIS o zip) y
   `build-macos` (`.app` + create-dmg) usando `setup-pixi` + `pixi run builder`.
3. Validar cada pipeline por SO en CI (Boltz se queda fuera de macOS: sin CUDA, §9 C12;
   QM se recomienda Linux: binarios de host).
4. **Codesigning Apple**: releases distribuibles en macOS exigen Developer ID +
   notarización (secrets de CI); sin firma, Gatekeeper bloquea el `.app` — definir si
   se compra cuenta Apple Developer o cada usuario firma localmente.
5. Riesgos a validar en la primera corrida: backend pywebview en WinForms y Qt
   WebEngine en macOS; NSIS/create-dmg del builder; presencia de `scripts/` en el
   payload por plataforma (el `.deb` actual no lo incluye, se prefiere source tree).

Referencias: `DOCS/consultorias/consultoria-12…§9` (matriz de compatibilidad),
`AGENTS.md` (estado actual), `.github/workflows/build.yml` (jobs reservados).

## R-ROAD-02 · Optimización de uso de GPU en Boltz (postergada por decisión del operador)

Observado el frente 2026-10-20: con `no_kernels: true` y modelos secuenciales, la GPU
trabaja en bursts (utilización media 2.8–5.2 %, pico 47 %, VRAM pico 4.6 GB por modelo
en RTX 5090). Palancas identificadas y documentadas:

- Activar kernels cuequivariance (cuequivariance + cuequivariance-torch 0.6.1, pinado):
  requiere bench emparejado GPU-only y validación de salida para el combo
  boltz 2.2.1 + cueq 0.6.1 (cueq salió 4 días antes que boltz 2.2.1, no testeado
  upstream).
- Paralelizar los 5 contenedores de modelos (`ThreadPoolExecutor`, GPU compartida por
  CDI).
- Subir `diffusion_samples` / `max_parallel_samples` en el perfil MAX.

Decisión del operador: mantener el comportamiento actual (estable, 2:58 para 5 modelos
en lysozyme). Revisar cuando haya proteínas grandes o lanzamientos upstream validados.
