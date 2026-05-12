# Research: Dashboard Integration Testing

**Purpose**: Resolve technical decisions for integrating Dash integration tests  
**Date**: 2026-05-12  
**Feature**: 002-dashboard-integration-tests

---

## Decision 1: Test Client Strategy

**Decision**: Two-tier approach — Flask test client for page-load tests, `dash_duo` for callback interaction tests.

**Rationale**:
- Flask test client (`app.server.test_client()`) requires no browser, runs in ~1s per page, ideal for CI without ChromeDriver
- `dash_duo` (Selenium) is needed to simulate real callback interactions (dropdown → graph update)
- Splitting keeps the suite fast: page-load tests run always, `dash_duo` tests run when browser is available

**Alternatives considered**:
- `dash_duo` only: requires ChromeDriver in CI, adds ~30s startup; overkill for simple render checks
- Flask client only: cannot test Dash callbacks (they require Dash's callback manager, not raw HTTP)

---

## Decision 2: Warehouse Data Mocking

**Decision**: Patch `pd.read_parquet` and the `_read_delta` helper with `pytest` fixtures returning minimal static DataFrames.

**Rationale**:
- Dashboard pages read warehouse data at module load via `pd.read_parquet()` or `_read_delta()`
- Patching at the function level via `unittest.mock.patch` avoids refactoring page modules
- Static DataFrames (3-5 rows) cover all rendering paths without requiring a Spark session

**Alternatives considered**:
- Real warehouse data: couples tests to data availability; not portable to CI
- Full mock of `config.py`: too broad, hides real config bugs

---

## Decision 3: Test Location & Marker

**Decision**: `tests/integration/` directory, `@pytest.mark.integration` marker.

**Rationale**:
- Keeps integration tests separate from unit (`tests/unit/`) and data-quality (`tests/data_quality/`)
- Existing `pytest.ini` already defines markers for `unit` and `data_quality`; adding `integration` is consistent
- CI can run `pytest -m integration` independently or alongside other markers

---

## Decision 4: Fixture Strategy for Dash App Instance

**Decision**: Conftest-level fixture creates the app once per session using `app.server.test_client()`.

**Rationale**:
- App instantiation is expensive (~2s); session-scoped fixture amortizes cost across all tests
- `dash_duo` fixture manages its own browser lifecycle per test function
- No shared mutable state between tests → safe to reuse app instance

---

## Summary: Implementation Approach

1. Add `tests/integration/conftest.py` with `client` fixture (Flask test client, session-scoped)
2. Add `tests/integration/test_pages.py` — parametrized over all 10 page URLs → assert 200
3. Add `tests/integration/test_callbacks.py` — `dash_duo` fixture for 3 callback interaction tests
4. Add `tests/integration/fixtures/` — static Pandas DataFrames per warehouse table
5. Patch `app.pages.[page]._read_delta` or `pd.read_parquet` in conftest autouse fixture
6. Register `integration` marker in `pytest.ini`
7. Add `dash[testing]` to `requirements.txt`
