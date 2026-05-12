# Implementation Plan: Secret Manager

**Branch**: `docs/architecture-specs` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)

---

## Summary

Create `src/secrets.py` with a `get_secret(name)` function that resolves secrets from: (1) environment variables, (2) HashiCorp Vault via `hvac`, (3) `.env` file fallback. Update `config.py` and `app/` to use `get_secret()` instead of direct `os.environ.get()` calls. Validate all required secrets at startup.

---

## Technical Context

**Primary backend**: HashiCorp Vault (self-hosted, KV v2 engine)  
**Library**: `hvac` (Vault Python client)  
**Fallback**: `.env` via `python-dotenv` (already used)  
**New file**: `src/secrets.py`  
**New dependency**: `hvac` in `requirements.txt`  
**Vault not required at dev time**: `.env` fallback covers local development

---

## Constitution Check

- [x] No hardcoded secrets — all secrets via `get_secret()`
- [x] `.env` remains functional for local dev (backward-compatible)
- [x] `config.py` role unchanged (technical settings) — secret values fetched via resolver, not stored in `config.py`
- [x] Vault URL and token from environment, not from code or `config.py`

**No constitution violations.**

---

## Project Structure

```text
src/
└── secrets.py          ← NEW: get_secret(), SecretProvider, startup validation

config.py               ← replace os.environ.get("SPOTIFY_CLIENT_ID") → get_secret("SPOTIFY_CLIENT_ID")

app/
└── (pages using secrets) ← replace direct env reads → get_secret()

requirements.txt        ← add hvac

.env.example            ← add VAULT_ADDR and VAULT_TOKEN documentation (commented out)
```

---

## Secret Resolution Order

```
1. os.environ.get(name)           → env vars (CI/Docker injection)
2. vault_client.secrets.kv.read(name)  → HashiCorp Vault (if VAULT_ADDR set)
3. dotenv_values(".env").get(name)     → .env file (local dev fallback)
4. raise MissingSecretError           → startup validation catches this
```

---

## Implementation Phases

### Phase 1: `src/secrets.py` Module

**Output**: Secret resolver with three-tier fallback  
**Dependencies**: None

```python
REQUIRED_SECRETS = [
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "TMDB_API_KEY",
    "TMDB_ACCESS_TOKEN",
]

def get_secret(name: str) -> str:
    # 1. Environment variable
    # 2. Vault (if VAULT_ADDR set)
    # 3. .env fallback
    # 4. raise MissingSecretError

def validate_secrets() -> None:
    """Call at startup — raises with list of all missing secrets."""
```

---

### Phase 2: Migrate Call Sites

**Output**: Zero direct `os.environ.get("SPOTIFY_*")` or `os.environ.get("TMDB_*")` calls outside `src/secrets.py`  
**Dependencies**: Phase 1

Files to update:
- `config.py` — any secret reads
- `app/pages/*.py` — any `os.environ` calls for API keys
- `app/utils/` — any secret reads in dashboard utilities

---

### Phase 3: Startup Validation

**Output**: `validate_secrets()` called at application entry point  
**Dependencies**: Phase 1–2

Call `validate_secrets()` in:
- `src/ingestion/run_all.py` — before any parser runs
- `app/app.py` or `app/server.py` — before Dash server starts

---

### Phase 4: Documentation

**Output**: Updated `.env.example` with Vault configuration docs  
**Dependencies**: None (parallel with Phase 1–3)

Add to `.env.example`:
```bash
# ── Secret Manager (optional — leave unset for .env fallback) ────────────────
# VAULT_ADDR=http://localhost:8200
# VAULT_TOKEN=your-vault-token
# VAULT_SECRET_PATH=mydigitaltwin/data/secrets
```

---

## Architecture Decisions

- **Three-tier fallback**: env → Vault → .env ensures CI, production, and local dev all work without code changes
- **`hvac` for Vault**: Official client, supports KV v2, token auth (simplest for self-hosted)
- **`validate_secrets()` at startup**: Fail fast with complete list — not scattered `KeyError` at runtime
- **No Vault required for local dev**: `.env` fallback makes the feature opt-in; no breaking change
