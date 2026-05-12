# Research: Secret Manager

**Date**: 2026-05-12

## Decision 1: Secret Manager backend

**Decision**: HashiCorp Vault (self-hosted) as the primary backend; `.env` as the local fallback.

**Rationale**: For a personal project, Vault is free and self-hosted (runs in Docker). AWS Secrets Manager and GCP Secret Manager require cloud accounts and incur costs. Vault's KV secrets engine is simple and well-documented with Python (`hvac` library). Azure Key Vault is also excluded for the same cost reason.

## Decision 2: Python library for Vault

**Decision**: `hvac` (official HashiCorp Vault Python client).

**Rationale**: Official, well-maintained, supports all Vault auth methods (token, AppRole, LDAP). `python-vault` is outdated. `hvac` is the standard choice.

## Decision 3: Provider abstraction pattern

**Decision**: `get_secret(name: str) -> str` function in a new `src/secrets.py` module.

**Rationale**: Callers (`config.py`, `app/`) call `get_secret("SPOTIFY_CLIENT_ID")` — they don't know whether it comes from Vault, AWS SM, or `.env`. This is the standard Secret Provider pattern. Alternative: inject a provider class — more complex, not needed for a single-backend scenario.

## Decision 4: Fallback order

**Decision**: Environment variable → Secret Manager → `.env` file.

**Rationale**: Environment variables (set by CI or Docker) take highest priority. Secret Manager second. `.env` file last (local dev fallback). This order ensures CI can inject secrets via env vars without a running Vault instance.

## Decision 5: Startup validation

**Decision**: Validate all required secrets at application startup using a `REQUIRED_SECRETS` list.

**Rationale**: Fail fast at startup with all missing secrets listed, rather than failing at runtime when the first missing secret is accessed. This is standard practice for 12-factor apps.
