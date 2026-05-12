# Tasks: Dashboard Integration Tests

**Input**: Design documents from `specs/002-dashboard-integration-tests/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

**Organization**: Tasks grouped by user story (P1 → P2 → P3), preceded by shared infrastructure setup.

---

## Phase 0: Setup & Configuration

**Purpose**: Test infrastructure scaffold — unblocks all user story phases.

- [ ] T001 Add `dash[testing]` to `requirements.txt`
- [ ] T002 Register `integration` marker in `pytest.ini` (add to `markers` list alongside `unit` and `data_quality`)
- [ ] T003 Create `tests/integration/__init__.py` (empty package marker)
- [ ] T004 Create `tests/integration/fixtures/` directory with one static DataFrame per warehouse table used by dashboard pages (`interest_profiles`, `behavioral_clusters`, `photo_clusters`)
- [ ] T005 Create `tests/integration/conftest.py` with:
  - Session-scoped `client` fixture: `app.server.test_client()`
  - Autouse `mock_warehouse` fixture: patches `clusters._read_delta` and `clusters._read_profiles` to return static DataFrames from `fixtures/`
- [ ] T006 Run `pytest tests/integration/ --collect-only` and confirm 0 errors

**Checkpoint**: Collection succeeds, no import errors, mocks verified ✅

---

## Phase 1: User Story 1 — Page-Load Tests (P1)

**Goal**: Every registered dashboard page returns HTTP 200 with non-empty body.

**Independent Test**: `pytest tests/integration/test_pages.py -v` passes for all 10 pages without live data.

- [ ] T007 [US1] Create `tests/integration/test_pages.py` with parametrized test over all 10 page URLs: `/`, `/clusters`, `/spotify`, `/netflix`, `/social`, `/photos`, `/memory-album`, `/psy`, `/timeline`, `/inventory`
- [ ] T008 [US1] Assert each page returns HTTP 200 and `len(response.data) > 0`
- [ ] T009 [US1] Mark tests with `@pytest.mark.integration`
- [ ] T010 [US1] Run `pytest tests/integration/test_pages.py -v` — fix any import or render errors until all 10 pass
- [ ] T011 [US1] Verify suite completes in under 30 seconds

**Checkpoint**: 10/10 page-load tests green, < 30s ✅

---

## Phase 2: User Story 2 — Callback Interaction Tests (P2)

**Goal**: Key interactive callbacks return valid output when triggered.

**Independent Test**: `pytest tests/integration/test_callbacks.py -v` with `dash_duo` passes for 3 callbacks.

- [ ] T012 [US2] Create `tests/integration/test_callbacks.py` using `dash_duo` fixture
- [ ] T013 [US2] Implement **Test 1 — Clusters dropdown**: select a cluster → assert graph output is a non-null Plotly figure dict with ≥ 1 trace
- [ ] T014 [US2] Implement **Test 2 — Spotify time filter**: apply time range → assert top-artists chart updates without rendering an error panel
- [ ] T015 [US2] Implement **Test 3 — None input fallback**: invoke callback with `None` input → assert empty-state component returned, no unhandled exception
- [ ] T016 [US2] Mark tests with `@pytest.mark.integration`
- [ ] T017 [US2] Run `pytest tests/integration/test_callbacks.py -v` — verify all 3 pass in < 90s (including browser startup)

**Checkpoint**: 3/3 callback tests green, < 90s ✅

---

## Phase 3: User Story 3 — Navbar Link Validation (P3)

**Goal**: All navbar links resolve to existing registered Dash page paths.

**Independent Test**: `pytest tests/integration/test_navbar.py -v` passes without browser or warehouse.

- [ ] T018 [US3] Create `tests/integration/test_navbar.py`
- [ ] T019 [US3] Extract all `href` attributes from `app/components/navbar.py`
- [ ] T020 [US3] Assert each `href` matches a path registered in `dash.page_registry`
- [ ] T021 [US3] Mark tests with `@pytest.mark.integration`
- [ ] T022 [US3] Run `pytest tests/integration/test_navbar.py -v` — fix any broken link references

**Checkpoint**: All navbar links validated ✅

---

## Phase 4: CI Integration & Polish

- [ ] T023 [P] Add integration test step to `.github/workflows/ci.yml`: `pytest -m integration -v --tb=short`
- [ ] T024 [P] Add `actions/setup-chrome` step in CI workflow (required for `dash_duo` Selenium tests)
- [ ] T025 Run full suite: `pytest -m integration -v` — confirm total time < 120s
- [ ] T026 [P] Run `ruff check tests/integration/` — fix any linting errors
- [ ] T027 Update `CONTRIBUTING.md` with integration test instructions and how to run with/without browser

**Checkpoint**: CI green, full suite < 120s, linting clean ✅

---

## Dependencies & Execution Order

```
Phase 0 (Setup) → Phase 1 (US1 Page-Load) → Phase 2 (US2 Callbacks) → Phase 3 (US3 Navbar) → Phase 4 (CI)
```

- **Phase 0**: No dependencies — start immediately
- **Phase 1**: Depends on Phase 0 (conftest + fixtures must exist)
- **Phase 2**: Depends on Phase 1 (app must render before testing callbacks)
- **Phase 3**: Independent of Phase 2 (no browser needed), can run after Phase 1
- **Phase 4**: Depends on all phases passing locally

### Parallel Opportunities

- T023 + T024 (CI config) can be written in parallel with Phase 3 tests
- T026 (linting) can run any time after code is written

---

## Summary

| Phase | User Story | Tasks | Gate |
|-------|------------|-------|------|
| 0 — Setup | — | T001–T006 | Collect OK, no import errors |
| 1 — P1 | Page-Load | T007–T011 | 10/10 HTTP 200, < 30s |
| 2 — P2 | Callbacks | T012–T017 | 3/3 callbacks pass, < 90s |
| 3 — P3 | Navbar | T018–T022 | All links valid |
| 4 — CI | Polish | T023–T027 | CI green, < 120s total |

**Total**: 27 tasks | **MVP scope**: Phases 0 + 1 (US1 page-load tests)

---

## Command Reference

```bash
# Run all integration tests
pytest -m integration -v --tb=short

# Run only page-load tests (no browser required)
pytest tests/integration/test_pages.py -v

# Run callback tests (requires ChromeDriver)
pytest tests/integration/test_callbacks.py -v

# Linting
ruff check tests/integration/

# Full suite timing check
pytest -m integration -v --tb=short --durations=10
```
