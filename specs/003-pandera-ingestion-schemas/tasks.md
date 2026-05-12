# Tasks: Pandera Ingestion Schemas

**Input**: Design documents from `specs/003-pandera-ingestion-schemas/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

**Organization**: Phase 1 (schema audit & fixes) → Phase 2 (test coverage verification)

**Note**: Schema files already exist for all 6 platforms. This is an audit and completion pass.

---

## Phase 1: Schema Audit & Fixes

**Purpose**: Ensure every schema covers all parser columns, has explicit `strict=False`, and includes at least one value constraint per table.

- [ ] T001 Cross-check `tests/schemas/twitter.py` against `TwitterParser.transform()` output in `src/ingestion/parsers/twitter.py` — add any missing columns
- [ ] T002 Add `raw_title: Column(str, nullable=False)` to `netflix_views` in `tests/schemas/netflix.py` (used in DQ duplicate check but absent from schema)
- [ ] T003 Add `strict=False` explicitly to all schema objects in `tests/schemas/netflix.py`
- [ ] T004 [P] Add `Check.str_length(min_value=1)` on `query` column in `google_searches` schema in `tests/schemas/google.py`
- [ ] T005 [P] Add `strict=False` explicitly to all schema objects in `tests/schemas/google.py`
- [ ] T006 [P] Add `strict=False` explicitly to all schema objects in `tests/schemas/spotify.py`
- [ ] T007 [P] Add `strict=False` explicitly to all schema objects in `tests/schemas/instagram.py`
- [ ] T008 [P] Add `strict=False` explicitly to all schema objects in `tests/schemas/tiktok.py`
- [ ] T009 [P] Add `strict=False` explicitly to all schema objects in `tests/schemas/twitter.py`
- [ ] T010 [P] Add `strict=False` explicitly to all schema objects in `tests/schemas/memory_album.py`

**Checkpoint**: `python -c "from tests.schemas.netflix import *; from tests.schemas.google import *; from tests.schemas.spotify import *; from tests.schemas.instagram import *; from tests.schemas.tiktok import *; from tests.schemas.twitter import *; from tests.schemas.memory_album import *"` exits 0 ✅

---

## Phase 2: Test Coverage Verification

**Purpose**: Confirm DQ test suite covers all updated schemas and collects without errors.

- [ ] T011 Run `pytest tests/data_quality/ --collect-only` — confirm 0 import errors and all 7 platform schema files are exercised
- [ ] T012 Verify `test_netflix_views_schema` in `tests/data_quality/test_dq_warehouse.py` reads `raw_title` column correctly (must not KeyError after schema update)
- [ ] T013 Run `ruff check tests/schemas/ tests/data_quality/` — fix any linting errors

**Checkpoint**: `pytest tests/data_quality/ --collect-only` exits 0, no import errors ✅

---

## Dependencies & Execution Order

```
T001 (twitter audit) → T009 (twitter strict=False)
T002–T003 (netflix fixes) — sequential (T003 after T002)
T004–T010 (other platform strict=False) — parallel with each other
Phase 2 (T011–T013) → depends on all Phase 1 tasks complete
```

### Parallel Opportunities

- T004–T010 can all be edited in parallel (different files)
- T011–T013 in Phase 2 are independent of each other once Phase 1 is done

---

## Summary

| Phase | Scope | Tasks | Gate |
|-------|-------|-------|------|
| 1 — Schema Fixes | 7 platform schema files | T001–T010 | All schema imports succeed |
| 2 — Verification | DQ test suite | T011–T013 | Collect OK, ruff clean |

**Total**: 13 tasks | **MVP scope**: T001–T010 (Phase 1 schema fixes)

---

## Command Reference

```bash
# Import check (all schemas)
python -c "from tests.schemas.netflix import *; from tests.schemas.google import *; from tests.schemas.spotify import *; from tests.schemas.instagram import *; from tests.schemas.tiktok import *; from tests.schemas.twitter import *; from tests.schemas.memory_album import *"

# Collect DQ tests (no live data needed)
pytest tests/data_quality/ --collect-only

# Run DQ tests (requires data/warehouse/ to be populated)
pytest -m data_quality -v --tb=short

# Linting
ruff check tests/schemas/ tests/data_quality/
```
