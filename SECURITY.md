# Security Policy

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of BIMOS seriously. If you believe you have found a security vulnerability, please **do not open a public issue**.

Instead, report it privately via:

- **GitHub Security Advisories**: https://github.com/RenatoJVA/BIMOS/security/advisories/new
- **Email**: *[private — reach out via GitHub Issues for contact]*

We will acknowledge receipt within 48 hours and provide a timeline for a fix and disclosure.

## Security Considerations

- BIMOS orchestrates third-party computational tools (Docker/Podman, GROMACS, AutoDock Vina, Boltz, ORCA, Gaussian). Ensure these tools are kept up to date and configured securely.
- The image pins Boltz `2.2.1`. Earlier releases are affected by
  [CVE-2025-70560](https://github.com/advisories/GHSA-fjm6-8xp2-4fwc)
  (HIGH): an insecure deserialization in Boltz's molecule loading, which
  unpickles molecule files without validation and can lead to arbitrary code
  execution. Exploitation requires an attacker to place a malicious file in a
  directory Boltz processes, so treat any third-party `.mol`/`.pkl` input as
  untrusted. Do not downgrade the pinned Boltz version in
  `backend/dockers/Dockerfile.bimos`.
- BIMOS ships **no tracking code**: no telemetry, analytics, or crash reporting. The only data that ever leaves your machine is what you explicitly trigger (Boltz MSA sequences, Boltz model-weight downloads, image pulls, or remote mode) — see [PRIVACY.md](./PRIVACY.md) for the full data policy.
- When using the remote/HPC mode (`BIMOS_REMOTE_URL`), ensure the connection is secured via a trusted network or VPN.
- The `.env` file contains API keys and paths to system binaries. It is excluded from version control by `.gitignore`. Do not commit it.
