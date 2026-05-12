# Implementation Plan: Ruff Style Rules

**Branch**: `docs/architecture-specs` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)

---

## Summary

Extend `pyproject.toml` to enable E, F, I, UP rule sets in ruff. Fix all existing violations across `src/`, `app/`, and `tests/` in a single migration PR. CI already runs `ruff check` — the change is additive (no CI config change needed).

---

## Technical Context

**Tool**: Ruff (already installed, already in CI)  
**Current rules**: E9, F63, F7, F82 (critical errors only)  
**Target rules**: E, F, I, UP  
**Line length**: 120 (unchanged)  
**Notebooks**: excluded (unchanged)

---

## Constitution Check

- [x] No hardcoded paths
- [x] No new dependencies — ruff already in requirements
- [x] CI already runs `ruff check` — extending rules, not adding a new step
- [x] Notebooks remain excluded

**No constitution violations.**

---

## Project Structure

```text
pyproject.toml             ← extend [tool.ruff.lint].select
src/ingestion/             ← fix violations
src/ingestion/parsers/     ← fix violations
app/                       ← fix violations (pages/, components/)
tests/                     ← fix violations (unit/, data_quality/, schemas/)
```

---

## Implementation Phases

### Phase 1: Audit Existing Violations

**Output**: Full list of current violations by rule category  
**Command**: `ruff check src/ app/ tests/ --select E,F,I,UP --statistics`

This gives a count per rule code — used to prioritize which fixes to batch.

---

### Phase 2: Fix Violations & Update Config

**Output**: Zero-violation codebase with extended ruff config  
**Dependencies**: Phase 1 audit

**Order of fixes** (least disruptive first):

1. **`I` (isort)**: `ruff check src/ app/ tests/ --select I --fix` — auto-fixable, zero manual work
2. **`UP` (pyupgrade)**: `ruff check src/ app/ tests/ --select UP --fix` — mostly auto-fixable
3. **`F` (Pyflakes)**: Fix unused imports, undefined names — mostly auto-fixable but review removals
4. **`E` (pycodestyle)**: Fix formatting violations — many auto-fixable via `ruff format`

**After fixes**, update `pyproject.toml`:

```toml
[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # Pyflakes
    "I",    # isort
    "UP",   # pyupgrade
]
```

**Validation**: `ruff check src/ app/ tests/` exits 0.

---

### Phase 3: CI Verification

**Output**: Confirmed CI passes with extended rules  
**Dependencies**: Phase 2

- Verify `.github/workflows/ci.yml` runs `ruff check .` (or equivalent) — no change needed if it does
- Run full test suite to confirm style fixes don't break logic: `pytest -m unit -v`

---

## Architecture Decisions

- **Big-bang migration**: Fix all violations in one PR — codebase is small enough, progressive migration leaves CI inconsistent
- **Auto-fix first**: Use `--fix` flag for isort and pyupgrade — reduces manual work; review diff before committing
- **No `noqa` unless necessary**: Prefer fixing the violation; `# noqa: <code>` only for intentional suppressions with documented reason
