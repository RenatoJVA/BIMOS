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

- BIMOS orchestrates third-party computational tools (Docker, GROMACS, AutoDock Vina, ORCA, Gaussian). Ensure these tools are kept up to date and configured securely.
- BIMOS does **not** collect, transmit, or store any personal or telemetry data.
- When using the remote/HPC mode (`BIMOS_REMOTE_URL`), ensure the connection is secured via a trusted network or VPN.
- The `.env` file contains API keys and paths to system binaries. It is excluded from version control by `.gitignore`. Do not commit it.
