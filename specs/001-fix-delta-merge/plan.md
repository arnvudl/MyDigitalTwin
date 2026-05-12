# Implementation Plan: Delta Lake MERGE Compliance

**Branch**: `001-fix-delta-merge` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-fix-delta-merge/spec.md`

**Status**: Compliance fix for Constitution Principle IV violations

## Summary

Fix 4 analytical notebooks to use Delta Lake `MERGE INTO` semantics instead of `.mode("overwrite")` and `.parquet()` writes. This ensures warehouse idempotency, data integrity, and compliance with MyDigitalTwin Constitution Principle IV (Delta Lake MERGE Only).

**Notebooks affected**:
1. `src/scripts/02_clusters/02_behavioral_clustering.ipynb` — Single `.mode("overwrite")` → MERGE
2. `src/scripts/02_clusters/03_fusion_visualization.ipynb` — `.parquet()` + `.mode("overwrite")` → Delta MERGE
3. `src/scripts/03_memory_album/01_visual_embeddings.ipynb` — `.mode('overwrite')` → MERGE
4. `src/scripts/03_memory_album/02_scene_clustering.ipynb` — Multiple `.mode('overwrite')` → MERGE

**Technical approach**: Replace all warehouse write patterns with idempotent Delta MERGE INTO operations using explicitly defined merge keys. All writes use Delta format, all reads remain unchanged.

## Technical Context (MyDigitalTwin-Specific)

**Language/Version**: Python 3.11

**Primary Dependencies**: PySpark 3.5.5, Delta Lake 3.2.0, Dash 4.1.0, Pandera (schemas), Ruff (linting)

**Storage**: Delta Lake (Parquet) file-based warehouse; no traditional RDBMS

**Testing**: pytest (unit + data_quality markers), Pandera schema validation

**Target Platform**: Docker (Spark container + Dash container); local Python 3.11

**Project Type**: Data pipeline + Analytics dashboard (monolithic)

**Performance Goals**: Incremental ingestion within bounds of Docker container memory

**Constraints**: 
- All paths from `config.py` (no hardcoding)
- Warehouse writes via `MERGE INTO` (never overwrite)
- Notebooks are idempotent

**Scale/Scope**: Multi-source GDPR data, 6+ platform parsers, 7 analytical notebooks

## Constitution Check

*GATE: Must comply with MyDigitalTwin Constitution before Phase 0 research.*

**This feature is a direct fix for Constitution violations. Passing these checks is the primary success criteria.**

### Checklist

- [x] Feature respects 3-tier config architecture (config.py, config.yaml, .env)
  - ✅ No changes to configuration; notebooks already use `config.WAREHOUSE`
- [x] No hardcoded paths; all from `config.py` via `os.path.join()`
  - ✅ All 4 notebooks already use `os.path.join(WAREHOUSE, table_name)` 
- [N/A] If ingestion: OVERWRITE strategy documented
  - ✅ Not applicable; this is an analytics fix, not ingestion
- [ ] **If warehouse write: Uses Delta Lake `MERGE INTO` (never `.mode("overwrite")`)**
  - ❌ **CURRENT VIOLATION**: All 4 notebooks use `.mode("overwrite")` or `.parquet()` on warehouse writes
  - ✅ **FIXED BY**: Replacing with Delta `MERGE INTO` semantics (PRIMARY DELIVERABLE)
- [N/A] If new parser: Extends `ParserBase`, registered in `run_all.py`
  - ✅ Not applicable; no parser changes
- [x] If new notebook: Numbered 01-07 in `src/scripts/`, uses `build_spark_session()`
  - ✅ All 4 notebooks are already in 02_clusters/ and 03_memory_album/; no renumbering needed
- [N/A] If dashboard: Page in `app/pages/`, reads from warehouse only
  - ✅ Not applicable; no dashboard changes
- [x] Test coverage: Unit tests in `tests/unit/`, data quality in `tests/data_quality/`
  - ✅ Existing test framework will validate MERGE behavior via re-run idempotency tests

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file
├── spec.md              # Feature specification with data schema (if applicable)
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root) — Data Pipeline Flow

```text
Data Ingestion Phase:
  data/inbox/                    # Raw GDPR exports (drop zone)
  src/ingestion/
  ├── base.py                    # ParserBase class
  ├── parsers/[platform].py      # NEW: Parser implementation (if Phase 1 task)
  └── run_all.py                 # Registration point
  data/processed/[PLATFORM]/     # Output: standardized tables

Analytics Phase:
  src/scripts/[NN_description]/  # NEW: Jupyter notebook (if Phase 2 task)
  data/warehouse/                # Output: Delta Lake tables (MERGE INTO)

Presentation Phase:
  app/
  ├── app.py                     # Dash entrypoint
  ├── pages/[feature].py         # NEW: Dashboard page (if Phase 3 task)
  ├── components/                # Shared navbar, filters
  └── assets/                    # CSS, JS, custom HTML

Quality Assurance:
  tests/
  ├── unit/                      # Fast tests, no dataset
  ├── data_quality/              # Slower, require warehouse
  └── schemas/[platform].py      # NEW: Pandera schema (if Phase 1 task)
```

## Implementation Phases

**Note**: This is a compliance fix to existing Phase 2 notebooks (Analytics), not a new feature phase.

### Phase 0: Research & Pattern Design

**Responsible**: Analytics Lead (or tech lead reviewing the fix)  
**Output**: `research.md` with Delta MERGE pattern documentation  
**When**: Before notebook modifications

**Deliverables**:
1. `research.md` — Document findings on:
   - Current write patterns in each notebook (location, table names, violations)
   - Delta MERGE INTO syntax for each use case (single table, multiple tables, schema-on-write)
   - Merge key strategy per notebook (cluster_id, image_id, scene_id, etc.)
   - Handling of initial table creation vs. incremental updates
   - Spark SQL vs. PySpark DataFrame API for MERGE operations

**Gating**: All 4 notebooks analyzed; merge key strategy confirmed.

---

### Phase 1: Fix Warehouse Writes (Modify 4 existing notebooks)

**Responsible**: Analytics Lead  
**Output**: 4 fixed notebooks using Delta MERGE INTO  
**When**: After Phase 0 research confirms pattern

**Deliverables**:
1. `src/scripts/02_clusters/02_behavioral_clustering.ipynb` — Replace `.write.format("delta").mode("overwrite").save(out_path)` with Delta MERGE pattern
2. `src/scripts/02_clusters/03_fusion_visualization.ipynb` — Replace `.write.mode("overwrite").parquet(out_path)` with Delta MERGE (multiple tables)
3. `src/scripts/03_memory_album/01_visual_embeddings.ipynb` — Replace `.mode('overwrite')` on embeddings with MERGE
4. `src/scripts/03_memory_album/02_scene_clustering.ipynb` — Replace all `.mode('overwrite')` calls with MERGE pattern

**Each notebook modification includes**:
   - Replace all warehouse write operations with `MERGE INTO` using explicit merge keys
   - Add markdown cell documenting merge key per table and MERGE strategy
   - Preserve all upstream transformations and input data validation
   - Ensure notebook remains idempotent (can be re-run without errors)

**Gating**: All 4 notebooks pass Ruff linting (`ruff check .`).

---

### Phase 2: Validation & Testing

**Responsible**: Analytics Lead (or test lead)  
**Output**: Verified idempotency and data integrity  
**When**: After Phase 1 notebook fixes complete

**Deliverables**:
1. Re-run each of the 4 notebooks twice with same input; verify:
   - No duplicate key errors
   - Row counts identical on run 1 and run 2 (idempotency)
   - Data values unchanged (no accidental transformations)
2. Run existing data quality tests: `pytest tests/data_quality/ -v`
3. Verify all warehouse tables report `Type: DELTA` via `DESCRIBE FORMATTED`
4. Document any schema updates or index requirements

**Gating**: All tests pass; idempotency confirmed for all 4 notebooks.

---

## Complexity Tracking

> **Fill ONLY if Constitution violations must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|-----------|--------------------------------------|
| [e.g., hardcoded path] | [reason] | [why config.py insufficient] |

---

## Implementation Order

**Critical path** (compliance-driven):
1. **Phase 0**: Research merge patterns (unblocks Phase 1)
2. **Phase 1**: Fix all 4 notebooks in parallel (they are independent)
3. **Phase 2**: Validate idempotency and test each notebook

**No external dependencies**. All 4 notebooks are independent; can be fixed in parallel.

---

## Testing Strategy

| Phase | Test Type | When | Gate |
|-------|-----------|------|------|
| Phase 0 (Research) | Code review | Before Phase 1 starts | All 4 notebooks analyzed; merge keys identified |
| Phase 1 (Fix) | Linting | After each notebook fix | `ruff check .` passes (0 errors) |
| Phase 1 (Fix) | Notebook execution | After linting | Each notebook runs without syntax errors |
| Phase 2 (Validation) | Idempotency | After Phase 1 complete | Re-run test: 5 consecutive runs produce identical output |
| Phase 2 (Validation) | Data quality | After Phase 1 complete | `pytest tests/data_quality/ -v` passes |
| Phase 2 (Validation) | Format compliance | After Phase 1 complete | All tables: `DESCRIBE FORMATTED [table_name]` → `Type: DELTA` |

---

## Dependency Chain

```
Phase 0 (Research)
    ↓
Phase 1 (Fix 4 notebooks) — can run in parallel
    ↓
Phase 2 (Validation)
```

Linear dependency: each phase depends on prior completion.

---

---

## Phase 0 Output: Research Artifacts

✅ **research.md** — Documents all findings and patterns
- Notebook-by-notebook analysis of current violations
- Merge key identification and validation strategy
- MERGE pattern recommendations per notebook
- Risk mitigation and edge case handling

---

## Phase 1 Output: Design Artifacts

✅ **data-model.md** — Entity definitions and merge strategies
- 5 warehouse entities: beh_clusters, interest_profiles, visual_embeddings, scene_clusters, scene_samples
- Merge keys per entity with uniqueness and stability validation
- Relationships and foreign keys
- Schema evolution handling

✅ **quickstart.md** — Copy-paste implementation templates
- 6 concrete code templates for MERGE patterns
- Before/after code examples
- Implementation checklist
- Common pitfalls and fixes
- Testing validation steps

---

## CI/CD Checks

All phases must pass before merge:
```bash
# Phase 1: Linting
ruff check .                             # No E9, F63, F7, F82 errors

# Phase 2: Validation (run against real warehouse data)
pytest tests/data_quality/ -v --tb=short # Data quality checks pass
# Manual: Re-run each of 4 notebooks; verify idempotency and row counts

# Integration: Container build
docker compose up --build                # Container builds without error
```

---

## Architecture Decision Summary

**Pattern choice**: Delta MERGE INTO over direct overwrite
- **Why**: Ensures idempotency (critical for notebooks that re-run), prevents data loss on failures, enables incremental updates
- **Alternative rejected**: Spark `coalesce().write.overwrite()` — doesn't provide merge semantics or partial updates
- **Alternative rejected**: Manual append + periodic compaction — adds operational complexity, breaks idempotency guarantee

**Merge key strategy**:
- Each notebook explicitly defines merge key(s) in markdown cell
- Merge key must be unique and stable across runs
- Handles both initial table creation and incremental updates

**No Spark session changes needed**:
- All notebooks already use `config.build_spark_session()`
- Delta Lake 3.x already available in `Dockerfile`
- No new dependencies required