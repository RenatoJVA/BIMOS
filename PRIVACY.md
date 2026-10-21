# Privacy & Data Policy — BIMOS

Last updated: 2026-09-29.

## 1. Local-First: Your Data Stays With You

BIMOS is a **local-first** application:

- No accounts, no telemetry, no analytics, no crash reporting. The BIMOS
  codebase contains no tracking code of any kind.
- Inputs, results, and job logs live on your machine, default
  `~/.bimos/workspace/` (configurable via `BIMOS_WORKSPACE`).
- The Boltz model weights and chemical component files are cached under
  `~/.bimos/cache/boltz/`. They are public data, not yours, but they are the
  largest thing BIMOS writes to disk (several GB): delete that directory to
  reclaim the space, and the next `predict` downloads it again.
- Deleting data is deleting files: `bimos jobs kill <ID>` stops a job;
  removing its workspace directory removes its data. No copies are kept
  anywhere else by BIMOS.

## 2. Data That Leaves Your Machine

Only in these cases, each triggered by your own configuration:

| Flow | What leaves | When | How to disable |
|------|-------------|------|----------------|
| Boltz MSA server | Your input **amino-acid sequence(s)** | Every `predict` with `use_msa_server: true` (the default) | Set `use_msa_server: false` in `~/.bimos/config/boltz.yaml` — this keeps your sequences local, but it does **not** make Boltz run on CPU: a GPU is still required either way |
| Boltz model weights and chemical component data | Standard connection metadata (IP, requested URLs) | The first `predict` on a machine, which downloads the model weights and the CCD/MOL component files into `~/.bimos/cache/boltz/` | N/A — required to predict at all. Once cached, prediction runs fully offline |
| Container / data downloads | Standard connection metadata (IP, requested URLs) | `bimos setup` pulls the base image, GROMACS sources, Vina binary, PyPI/GitHub packages | N/A — required to build the image; use a clean build environment if this matters |
| Remote mode | Everything the UI sends (jobs, files, logs) | Only if **you** set `BIMOS_REMOTE_URL` (thin-client mode) | Leave it blank for fully local execution |

Weight and component downloads are plain HTTPS requests to the Boltz model
gateway and to `boltz-community/boltz-2` on Hugging Face. They carry no
sequence or structure data: those files are the same for every user. Nothing
identifying you is sent, because no account is used.

ORCA / Gaussian 16 run as **local host processes** on files you own;
BIMOS sends nothing about them anywhere.

## 3. Sensitive Sequences

Protein sequences can be sensitive (unpublished research, proprietary
targets). If that applies to you, either disable the MSA server (above)
or run predictions on an isolated machine. Note that with
`use_msa_server: false` Boltz relies on the single-sequence template path,
which lowers prediction quality — a GPU is still required in that mode.
BIMOS cannot control what the external MSA service does with submitted
sequences — consult that service's policy before submitting confidential
data.

## 4. Your Responsibilities

- Keep `~/.bimos/` (workspace, `.env` with paths, job history) on
  encrypted storage if it holds sensitive data; restrict file permissions.
- Before sharing `screen_report.csv`, logs, or workspaces, check them for
  sensitive sequences or paths — they are plain files under your control.

## 5. Changes

Material changes to this policy are noted in
[CHANGELOG.md](./CHANGELOG.md).
