# Tasks: Secret Manager

**Input**: Design documents from `specs/010-secret-manager/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

---

## Phase 1: secrets.py Module

- [ ] T001 Add `hvac` to `requirements.txt`
- [ ] T002 Create `src/secrets.py` with:
  - `REQUIRED_SECRETS` list (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `TMDB_API_KEY`, `TMDB_ACCESS_TOKEN`)
  - `MissingSecretError(Exception)` class
  - `get_secret(name: str) -> str` with 3-tier resolution: (1) `os.environ.get()`, (2) Vault via `hvac` if `VAULT_ADDR` is set, (3) `.env` via `dotenv_values(".env")`; raise `MissingSecretError` if all three miss
  - `validate_secrets() -> None` that calls `get_secret()` for every entry in `REQUIRED_SECRETS` and raises with the full list of missing secrets

**Checkpoint**: `python -c "from src.secrets import get_secret, validate_secrets"` exits 0 ✅

---

## Phase 2: Migrate Call Sites

- [ ] T003 Audit all `os.environ.get()` and `os.environ["KEY"]` calls in `config.py` — replace any that reference secret keys (SPOTIFY_*, TMDB_*) with `get_secret()`
- [ ] T004 [P] Audit `app/pages/*.py` for direct env reads of secret keys — replace with `get_secret()`
- [ ] T005 [P] Audit any other files in `app/` or `src/` for direct secret env reads — replace with `get_secret()`

**Checkpoint**: `grep -r "SPOTIFY_CLIENT_ID\|TMDB_API_KEY" src/ app/ --include="*.py" | grep -v "secrets.py"` returns no matches ✅

---

## Phase 3: Startup Validation

- [ ] T006 Add `validate_secrets()` call to `src/ingestion/run_all.py` before any parser runs
- [ ] T007 Add `validate_secrets()` call to the Dash app entry point (`app/app.py` or `app/server.py`) before `app.run_server()`
- [ ] T008 Run `pytest -m unit -v` — confirm no unit tests break after migration

**Checkpoint**: Application fails with clear `MissingSecretError` listing missing secrets when `.env` is absent and Vault not configured ✅

---

## Phase 4: Documentation

- [ ] T009 Update `.env.example` to add commented-out Vault configuration section (`VAULT_ADDR`, `VAULT_TOKEN`, `VAULT_SECRET_PATH`) with brief instructions

**Checkpoint**: `.env.example` documents both .env and Vault usage ✅

---

## Dependencies & Execution Order

```
T001 → T002 (module creation)
T002 → T003–T005 (migration, can be parallel)
T003–T005 → T006–T008 (startup validation)
T009 — independent (documentation)
```

---

## Summary

| Phase | Scope | Tasks | Gate |
|-------|-------|-------|------|
| 1 — Module | src/secrets.py | T001–T002 | Module imports, get_secret works |
| 2 — Migration | config.py, app/ | T003–T005 | No direct env reads of secrets |
| 3 — Startup | run_all.py, app.py | T006–T008 | Fail-fast validation works |
| 4 — Docs | .env.example | T009 | Vault docs present |

**Total**: 9 tasks | **MVP scope**: T001–T002 (module only, migration optional)

---

## Command Reference

```bash
# Verify no remaining direct secret reads
grep -r "SPOTIFY_CLIENT_ID\|TMDB_API_KEY\|SPOTIFY_CLIENT_SECRET\|TMDB_ACCESS_TOKEN" src/ app/ --include="*.py" | grep -v "secrets.py"

# Test resolver with .env
python -c "from src.secrets import get_secret; print(get_secret('SPOTIFY_CLIENT_ID'))"

# Test startup validation (should fail if secrets missing)
python -c "from src.secrets import validate_secrets; validate_secrets()"
```
