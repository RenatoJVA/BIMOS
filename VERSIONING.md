# Versioning Policy

BIMOS follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## Summary

Given a version number **MAJOR.MINOR.PATCH**:

- **MAJOR** — incompatible API changes
- **MINOR** — backwards-compatible functionality additions
- **PATCH** — backwards-compatible bug fixes

## Current version

**0.1.0** — initial development release. The public API is not yet stable.
Once the public API (see consultoría-09, M2) is published on PyPI,
the version will move to 1.0.0.

## Pre-release labels

Pre-release versions use the format `MAJOR.MINOR.PATCH-alpha.N`,
`MAJOR.MINOR.PATCH-beta.N`, or `MAJOR.MINOR.PATCH-rc.N`.

## Commit convention

All commits should follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — MINOR bump
- `fix:` — PATCH bump
- `feat!:` or `fix!:` — MAJOR bump
- `refactor:`, `test:`, `docs:`, `ci:`, `chore:` — no bump
