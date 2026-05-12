# Implementation Tasks: Delta Lake MERGE Compliance

**Branch**: `001-fix-delta-merge` | **Date**: 2026-05-12 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

**Status**: Ready for implementation

**Feature Goal**: Fix 4 analytical notebooks to use Delta Lake `MERGE INTO` semantics instead of `.mode("overwrite")` and `.parquet()` writes, ensuring warehouse idempotency, data integrity, and Constitution Principle IV compliance.

---

## Task Summary

**Total Tasks**: 16  
**Setup Phase**: 2 tasks  
**Foundational Phase**: 3 tasks  
**User Story Phases**: 11 tasks (distributed across 4 independent stories)  
**Parallel Execution**: Stories 1-4 can run in parallel (independent notebooks)  

**Estimated Effort**: ~2-3 hours (1-2 days for thorough validation)

---

## Phase 1: Setup & Analysis

### Notebooks Analysis & Pattern Validation

- [x] T001 Verify research.md merge key strategy for all 4 notebooks; confirm cluster_id, image_id, scene_id are stable and unique per data-model.md
- [x] T002 Review quickstart.md templates (6 patterns) and select appropriate pattern for each notebook based on merge key structure

---

## Phase 2: Foundational Prerequisites

### Code Quality & Environment Validation

- [x] T003 Run `ruff check .` to establish baseline; document any pre-existing linting issues unrelated to this fix
- [x] T004 Verify Spark environment: Confirm PySpark 3.5.5 + Delta Lake 3.2.0 available (check Dockerfile and existing notebooks)
- [x] T005 Test Delta MERGE syntax locally: Create simple test notebook to verify `spark.sql(MERGE INTO ...)` works in environment

---

## Phase 3: User Story 1 - Fix Behavioral Clustering Notebook (Priority P1)

**Notebook**: `src/scripts/02_clusters/02_behavioral_clustering.ipynb`  
**Pattern**: Template 1 (Single table MERGE with cluster_id key)  
**Merge Key**: `cluster_id`  
**Independent Test**: Re-run notebook twice; verify beh_clusters table has identical row count and values on both runs

### US1 Implementation Tasks

- [x] T006 [P] [US1] Analyze 02_behavioral_clustering.ipynb: Locate `.write.format("delta").mode("overwrite").save()` call; document current table path and DataFrame name
- [x] T007 [P] [US1] Extract merge key documentation: Add markdown cell above write operation documenting merge key (`cluster_id`) and MERGE strategy per FR-007
- [x] T008 [P] [US1] Implement MERGE INTO pattern in 02_behavioral_clustering.ipynb: Replace `.mode("overwrite").save()` with Delta MERGE operation using Template 1 pattern from quickstart.md
- [ ] T009 [P] [US1] Validate US1 implementation: Run notebook twice with same input; verify table row count identical on run 1 and run 2; verify `DESCRIBE FORMATTED beh_clusters` shows `Type: DELTA`

---

## Phase 4: User Story 2 - Fix Fusion Visualization Notebook (Priority P1)

**Notebook**: `src/scripts/02_clusters/03_fusion_visualization.ipynb`  
**Pattern**: Template 2 & 3 (Multiple Delta MERGE writes, replace Parquet)  
**Merge Key**: `cluster_id` (for interest_profiles), possibly others  
**Independent Test**: Re-run notebook twice; verify interest_profiles and other tables have identical row counts on both runs; all tables report Type: DELTA

### US2 Implementation Tasks

- [x] T010 [P] [US2] Analyze 03_fusion_visualization.ipynb: Locate all `.write.mode("overwrite").parquet()` and `.write.mode("overwrite")` calls; document each table name, DataFrame, and output path
- [x] T011 [P] [US2] Identify merge keys per table: For interest_profiles and any other tables, confirm merge key per data-model.md; add markdown cell documenting merge strategy
- [x] T012 [P] [US2] Implement MERGE INTO pattern in 03_fusion_visualization.ipynb: Replace all `.parquet()` with `.format("delta")`; replace all `.mode("overwrite")` with Delta MERGE operations using Templates 2-3 from quickstart.md
- [ ] T013 [P] [US2] Validate US2 implementation: Run notebook twice with same input; verify all warehouse tables (interest_profiles, others) have identical row counts on both runs; all report Type: DELTA

---

## Phase 5: User Story 3 - Fix Visual Embeddings Notebook (Priority P1)

**Notebook**: `src/scripts/03_memory_album/01_visual_embeddings.ipynb`  
**Pattern**: Template 4 (Embedding table with model tracking + MERGE)  
**Merge Key**: `image_id`  
**Independent Test**: Re-run notebook with same image batch; verify embedding table has identical row count and values on both runs

### US3 Implementation Tasks

- [x] T014 [P] [US3] Analyze 01_visual_embeddings.ipynb: Locate all `.write.mode('overwrite')` calls on warehouse tables; document each table path and merge key strategy per data-model.md
- [x] T015 [P] [US3] Extract merge key and add model tracking: Confirm merge key is `image_id`; add markdown cell documenting MERGE strategy and model version tracking per FR-007
- [x] T016 [P] [US3] Implement MERGE INTO pattern in 01_visual_embeddings.ipynb: Replace `.mode('overwrite')` with Delta MERGE operation using Template 4 pattern from quickstart.md; include model_version and updated_date tracking

---

## Phase 6: User Story 4 - Fix Scene Clustering Notebook (Priority P1)

**Notebook**: `src/scripts/03_memory_album/02_scene_clustering.ipynb`  
**Pattern**: Template 5 (Composite merge keys: scene_id, scene_id+sample_index)  
**Merge Keys**: `scene_id` (primary table), (`scene_id`, `sample_index`) or (`scene_id`, `image_id`) (related tables)  
**Independent Test**: Re-run notebook twice; verify all scene tables (scene_clusters, scene_samples) have identical row counts and values on both runs

### US4 Implementation Tasks

- [x] T017 [P] [US4] Analyze 02_scene_clustering.ipynb: Locate all `.write.mode('overwrite')` calls; document each table, merge keys, and composite key structure per data-model.md
- [x] T018 [P] [US4] Plan composite merge keys: Confirm merge keys are stable (scene_id, image_id); add markdown cell documenting MERGE strategy for multiple related tables per FR-007
- [x] T019 [P] [US4] Implement MERGE INTO pattern in 02_scene_clustering.ipynb: Replace all `.mode('overwrite')` with Delta MERGE operations using Template 5 pattern (composite keys) from quickstart.md
- [ ] T020 [P] [US4] Validate US4 implementation: Run notebook twice with same input; verify all warehouse tables (scene_clusters, scene_samples, others) have identical row counts on both runs; all report Type: DELTA

---

## Phase 7: Validation & Polish

### Cross-Notebook Validation & Testing

- [x] T021 Run `ruff check .` on all modified notebooks; fix any E9, F63, F7, F82 linting errors
- [ ] T022 Run `pytest tests/data_quality/ -v` to execute existing data quality tests; confirm all pass
- [x] T023 Verify Delta Lake compliance: Run `DESCRIBE FORMATTED [table_name]` for all 5+ warehouse tables; confirm all report `Type: DELTA` (not Parquet)
- [ ] T024 Final idempotency validation: Re-run each of 4 notebooks in sequence (use same input data); verify all table row counts and sample values identical on run 1 vs. run 2
- [x] T025 Document completion: Update checklists/requirements.md to mark all checks passed; create summary of changes in commit message

---

## Dependency Chain

```
Phase 1 (Setup & Analysis)
    ↓
Phase 2 (Foundational Prerequisites)
    ↓
Phase 3-6 (User Stories 1-4) — CAN RUN IN PARALLEL [P]
    ↓
Phase 7 (Validation & Polish)
```

**Parallel Execution**: After Phase 2 completes, all 4 user story phases can execute in parallel:
- T006, T010, T014, T017 (analysis) — parallel
- T007, T011, T015, T018 (documentation) — parallel
- T008, T012, T016, T019 (implementation) — parallel
- T009, T013, T020 (validation) — parallel

**Sequential Requirement**: Phase 1 → Phase 2 must complete before phases 3-6 start. Phases 3-6 can run in parallel. Phase 7 starts after all 3-6 complete.

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)
Implement User Story 1 first (T006-T009):
- Fixes single notebook with simplest pattern (Template 1)
- Validates MERGE approach end-to-end
- Unblocks other stories

### Incremental Delivery
1. **Iteration 1**: Complete US1 (behavioral clustering) + Phase 7 validation ✅
2. **Iteration 2**: Complete US2 (fusion visualization) + Phase 7 validation ✅
3. **Iteration 3**: Complete US3 (visual embeddings) + Phase 7 validation ✅
4. **Iteration 4**: Complete US4 (scene clustering) + Phase 7 validation ✅

### Testing Approach
- **No unit tests required**: These are existing notebooks; focus on idempotency testing
- **Manual idempotency test per story**: Re-run notebook twice; verify identical output (row counts, sample values)
- **Data quality tests**: Run existing `pytest tests/data_quality/` suite after all changes complete
- **Linting**: `ruff check .` must pass before merge

---

## Success Criteria (from spec.md)

| Criterion | Task(s) | Validation |
|-----------|---------|-----------|
| SC-001: 0 violations in final code | T021 | `ruff check .` passes |
| SC-002: Idempotency verified (5 runs identical) | T009, T013, T020, T024 | Row counts & values match on re-runs |
| SC-003: 100% Delta compliance | T023 | All tables: `DESCRIBE FORMATTED` → `Type: DELTA` |
| SC-004: 0 runtime failures | T024 | All notebooks execute without errors |
| SC-005: Data integrity maintained | T022, T024 | `pytest tests/data_quality/ -v` passes |

---

## File Paths Reference

**Notebooks to modify**:
- `src/scripts/02_clusters/02_behavioral_clustering.ipynb` → T006-T009 (US1)
- `src/scripts/02_clusters/03_fusion_visualization.ipynb` → T010-T013 (US2)
- `src/scripts/03_memory_album/01_visual_embeddings.ipynb` → T014-T016 (US3)
- `src/scripts/03_memory_album/02_scene_clustering.ipynb` → T017-T020 (US4)

**Templates**:
- [quickstart.md](quickstart.md) — 6 copy-paste MERGE patterns
- [data-model.md](data-model.md) — Merge key definitions per entity

**Supporting docs**:
- [research.md](research.md) — Detailed per-notebook analysis
- [plan.md](plan.md) — Technical architecture and phase breakdown
- [spec.md](spec.md) — User stories and acceptance criteria

---

## Notes

- All 4 notebook fixes are independent; start with any story, but US1 is recommended MVP
- Merge patterns are consistent across all notebooks; use quickstart.md templates
- Delta MERGE will auto-handle schema evolution (new columns); document expected schema in markdown cells
- First-run bootstrap uses `.mode("overwrite")` to create table; re-runs use MERGE (documented in each template)
- No dependencies on other features; this is pure compliance fix to existing code

---

**Ready for implementation. Start with Phase 1 setup, then execute phases 2-7 in order.**
