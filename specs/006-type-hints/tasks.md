# Tasks: Type Hints (Core Modules)

**Input**: Design documents from `specs/006-type-hints/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

---

## Phase 1: ParserBase Annotations

- [ ] T001 Annotate all method signatures in `src/ingestion/base.py`: `__init__`, `move() -> None`, `transform() -> pd.DataFrame`, `load(df: pd.DataFrame) -> None`, `detect_source() -> str | None` and all helpers; add `from __future__ import annotations` at top if needed for forward references

**Checkpoint**: `mypy src/ingestion/base.py --ignore-missing-imports` exits 0 ✅

---

## Phase 2: Parser Annotations

- [ ] T002 [P] Annotate all public methods in `src/ingestion/parsers/instagram.py`
- [ ] T003 [P] Annotate all public methods in `src/ingestion/parsers/spotify.py`
- [ ] T004 [P] Annotate all public methods in `src/ingestion/parsers/google.py`
- [ ] T005 [P] Annotate all public methods in `src/ingestion/parsers/netflix.py`
- [ ] T006 [P] Annotate all public methods in `src/ingestion/parsers/tiktok.py`
- [ ] T007 [P] Annotate all public methods in `src/ingestion/parsers/twitter.py`

**Checkpoint**: `mypy src/ingestion/parsers/ --ignore-missing-imports` exits 0 ✅

---

## Phase 3: Orchestrator & Config

- [ ] T008 Annotate public functions in `src/ingestion/run_all.py`: entry point, loop variables, any helper functions
- [ ] T009 Annotate public functions in `config.py`: `build_spark_session() -> SparkSession`, path constants typed as `Path`; add `# type: ignore[import]` for pyspark import if needed

**Checkpoint**: `mypy src/ingestion/ --ignore-missing-imports` exits 0 ✅

---

## Phase 4: CI Integration

- [ ] T010 Add `mypy` to `requirements.txt`
- [ ] T011 Add mypy step to `.github/workflows/ci.yml`: `mypy src/ingestion/ --ignore-missing-imports` with `continue-on-error: true` initially; remove flag once clean
- [ ] T012 Run `pytest -m unit -v` — confirm annotations don't break any unit tests

**Checkpoint**: CI green, mypy step present ✅

---

## Dependencies & Execution Order

```
T001 (base.py) → T002–T007 (parsers, parallel) → T008–T009 (orchestrator + config) → T010–T012 (CI)
```

---

## Summary

| Phase | Scope | Tasks | Gate |
|-------|-------|-------|------|
| 1 — ParserBase | base.py | T001 | mypy base.py exits 0 |
| 2 — Parsers | 6 parser files | T002–T007 | mypy parsers/ exits 0 |
| 3 — Orchestrator | run_all.py, config.py | T008–T009 | mypy src/ingestion/ exits 0 |
| 4 — CI | requirements.txt, ci.yml | T010–T012 | CI green |

**Total**: 12 tasks | **MVP scope**: T001–T009 (full annotation, no CI yet)

---

## Command Reference

```bash
# Check single file
mypy src/ingestion/base.py --ignore-missing-imports

# Check all ingestion
mypy src/ingestion/ --ignore-missing-imports

# Check with error codes (helpful for noqa comments)
mypy src/ingestion/ --ignore-missing-imports --show-error-codes
```
