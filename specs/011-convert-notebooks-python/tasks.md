# Tasks: Convert Analytical Notebooks to Production Python Scripts

**Feature**: 011-convert-notebooks-python  
**Branch**: `011-convert-notebooks-python`  
**Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)  
**Generated**: 2026-05-13

---

## Summary

- **Total tasks**: 26
- **Phase 1 (Setup)**: 3 tasks
- **Phase 2 (Foundational)**: 2 tasks
- **Phase 3 — US1 (Single Script Execution)**: 15 tasks (one per notebook conversion)
- **Phase 4 — US2 (Full Pipeline)**: 1 task
- **Phase 5 — US3 (Validation Script)**: 1 task
- **Phase 6 (Polish)**: 4 tasks
- **Parallel opportunities**: All US1 conversion tasks within each group [P]

---

## Implementation Strategy

**MVP scope (Phase 1 + 2 + Phase 3 US1)**: Convert all 15 notebooks to `.py` scripts. Once each script runs independently, US1 is complete.

**Incremental delivery**:
1. Phase 1 → templates ready
2. Phase 3 (groups B–F) → 15 scripts converted (can be done in parallel within each group)
3. Phase 4 → `run_pipeline.py` wires them together
4. Phase 5 → `validate_outputs.py` validates correctness
5. Phase 6 → linting and documentation

---

## Phase 1: Setup

> Initialize project structure and script templates before any notebook conversion.

- [x] T001 Create Spark script template file `src/scripts/_template_spark.py` following plan.md Phase A (try/finally, build_spark_session, sys.path root detection)
- [x] T002 Create pure-Python script template file `src/scripts/_template_pure_python.py` following plan.md Phase A (no Spark, sys.path root detection, config imports)
- [x] T003 Verify `config.py` exports: `build_spark_session`, `PROCESSED_DATA`, `WAREHOUSE` — read the file and confirm all three are present; note any missing paths needed by notebooks

---

## Phase 2: Foundational

> Create the skeleton files for orchestration and validation before filling them with logic.

- [x] T004 Create `run_pipeline.py` skeleton at project root with 19-stage list (see data-model.md), argparse for `--stage`, `--from`, `--to`, and `subprocess.run()` dispatch loop — leave stage implementations as stubs
- [x] T005 Create `validate_outputs.py` skeleton at project root with expectations dict (all tables from data-model.md), Delta read loop, pass/fail reporting, and `sys.exit(0/1)` — leave actual Delta reads as stubs

---

## Phase 3: User Story 1 — Run a Single Analytical Script

> **Goal**: Each of the 15 converted scripts runs independently via `python src/scripts/<folder>/<script>.py` without errors.  
> **Independent test**: `python src/scripts/01_exploration/instagram.py` writes Delta table and exits cleanly.

### Group B — 01_exploration (6 scripts, all parallelizable)

- [x] T006 [P] [US1] Convert `src/scripts/01_exploration/instagram.ipynb` → `src/scripts/01_exploration/instagram.py`: copy transform + MERGE logic, remove PARQUET_DIR hardcode, remove all .show()/.printSchema()/exploration cells, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin - Instagram" driver_memory="4g" shuffle_partitions=8
- [x] T007 [P] [US1] Convert `src/scripts/01_exploration/google_youtube.ipynb` → `src/scripts/01_exploration/google_youtube.py`: copy transform + MERGE logic, remove exploration cells, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin - Google" driver_memory="6g" shuffle_partitions=8
- [x] T008 [P] [US1] Convert `src/scripts/01_exploration/spotify.ipynb` → `src/scripts/01_exploration/spotify.py`: copy transform + MERGE logic, remove exploration cells, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin - Spotify" driver_memory="4g" shuffle_partitions=8
- [x] T009 [P] [US1] Convert `src/scripts/01_exploration/tiktok.ipynb` → `src/scripts/01_exploration/tiktok.py`: copy transform + MERGE logic, remove exploration cells, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin - TikTok" driver_memory="4g" shuffle_partitions=8
- [x] T010 [P] [US1] Convert `src/scripts/01_exploration/twitter.ipynb` → `src/scripts/01_exploration/twitter.py`: copy transform + MERGE logic, remove exploration cells, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin - Twitter" driver_memory="4g" shuffle_partitions=8
- [x] T011 [P] [US1] Convert `src/scripts/01_exploration/netflix.ipynb` → `src/scripts/01_exploration/netflix.py`: copy transform + MERGE logic, remove exploration cells, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin - Netflix" driver_memory="4g" shuffle_partitions=8

### Group C — 02_clusters (3 scripts, all parallelizable; depend on Group B outputs at runtime)

- [x] T012 [P] [US1] Convert `src/scripts/02_clusters/01_content_clustering.ipynb` → `src/scripts/02_clusters/01_content_clustering.py`: copy clustering logic, remove matplotlib/seaborn imports and plot calls, use delete()+append write pattern (computed table), wrap in main()+try/finally, spark params: app_name="MyDigitalTwin-FrequencyAnalysis" driver_memory="4g" shuffle_partitions=8 delta=True
- [x] T013 [P] [US1] Convert `src/scripts/02_clusters/02_behavioral_clustering.ipynb` → `src/scripts/02_clusters/02_behavioral_clustering.py`: copy clustering logic, remove visualization cells, use delete()+append pattern, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin-BehavioralClustering" driver_memory="4g" shuffle_partitions=8
- [x] T014 [P] [US1] Convert `src/scripts/02_clusters/03_fusion_visualization.ipynb` → `src/scripts/02_clusters/03_fusion_visualization.py`: copy merge/fusion logic (NOT visualization), remove ALL matplotlib/seaborn imports and plot calls, use delete()+append pattern, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin-FusionViz" driver_memory="4g" shuffle_partitions=8

### Group D — 03_memory_album (3 scripts, all parallelizable)

- [x] T015 [P] [US1] Convert `src/scripts/03_memory_album/01_visual_embeddings.ipynb` → `src/scripts/03_memory_album/01_visual_embeddings.py`: keep Spark only for reading photo paths and writing embeddings (BLIP-2/CLIP inference stays outside Spark), photo_embeddings→MERGE on photo_id, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin-MemoryAlbum-Embeddings" driver_memory="4g" shuffle_partitions=8 snappy=True delta=True
- [x] T016 [P] [US1] Convert `src/scripts/03_memory_album/02_scene_clustering.ipynb` → `src/scripts/03_memory_album/02_scene_clustering.py`: copy clustering logic, scenes+scene_centroids→delete()+append, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin-MemoryAlbum-Clustering" driver_memory="4g" shuffle_partitions=8
- [x] T017 [P] [US1] Convert `src/scripts/03_memory_album/03_music_matching.ipynb` → `src/scripts/03_memory_album/03_music_matching.py`: copy music-matching logic, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin-MemoryAlbum-MusicMatching" driver_memory="4g" shuffle_partitions=8

### Group E — 05_CLIP (2 scripts, both parallelizable; do NOT touch 00_collect_photos.py)

- [x] T018 [P] [US1] Convert `src/scripts/05_CLIP/01_clip_embeddings.ipynb` → `src/scripts/05_CLIP/01_clip_embeddings.py`: read pre-computed CLIP embeddings from 00_collect_photos.py output, write to warehouse, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin-CLIP-Embeddings" driver_memory="4g" shuffle_partitions=8 snappy=True delta=True
- [x] T019 [P] [US1] Convert `src/scripts/05_CLIP/02_clip_clustering.ipynb` → `src/scripts/05_CLIP/02_clip_clustering.py`: copy clustering logic, keep .cache() usage (legitimate per research.md), photo_clusters→delete()+append, wrap in main()+try/finally, spark params: app_name="MyDigitalTwin-CLIP-Clustering-V2" driver_memory="4g" shuffle_partitions=8 delta=True

### Group F — 06_social (1 script, pure Python — no Spark)

- [x] T020 [US1] Convert `src/scripts/06_social/01_social_graph.ipynb` → `src/scripts/06_social/01_social_graph.py`: use pure-Python template (NO build_spark_session, NO spark.stop()), keep JSON graph construction logic (~100 nodes max), remove NetworkX/matplotlib visualization cells, write output via json/pandas using paths from config.py

---

## Phase 4: User Story 2 — Run the Full Pipeline End-to-End

> **Goal**: `python run_pipeline.py` executes all 19 stages sequentially; `--stage`, `--from`, `--to` args work.  
> **Independent test**: `python run_pipeline.py --stage instagram` runs only stage 01 without errors.

- [x] T021 [US2] Complete `run_pipeline.py` at project root: wire all 19 stages (data-model.md order) with `subprocess.run([sys.executable, script_path], check=True)`, implement `--stage <name>` (match by script filename), `--from <N>` and `--to <N>` (1-indexed stage range), print stage name + status on start and completion, exit with failing stage info on error

---

## Phase 5: User Story 3 — Validate Conversion Correctness

> **Goal**: `python validate_outputs.py` checks schema + row counts; exits 0 on pass, 1 on fail.  
> **Independent test**: Running the validator after the full pipeline exits 0 with all tables passing.

- [x] T022 [US3] Complete `validate_outputs.py` at project root: build a Spark session with driver_memory="1g" shuffle_partitions=2, implement expectations dict for all converted-script output tables (min_rows, required_columns), for each table: check Delta table exists at WAREHOUSE path, read schema, count rows, report "✓ table — schema OK, N rows" or "✗ table — MISSING / schema mismatch / 0 rows", exit code 0 if all pass else 1

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T023 Run `ruff check .` from project root and fix all lint errors in newly created `.py` files (converted scripts, run_pipeline.py, validate_outputs.py)
- [x] T024 Verify no existing scripts were modified: run `git diff --name-only` and confirm `src/scripts/04_clone/`, `src/scripts/07_psy/`, `src/scripts/05_CLIP/00_collect_photos.py`, `src/scripts/03_memory_album/scripts/` are not in the diff
- [x] T025 Delete template helper files `src/scripts/_template_spark.py` and `src/scripts/_template_pure_python.py` (they were scaffolding only, not production files)
- [x] T026 Update `specs/011-convert-notebooks-python/plan.md` implementation status: mark each phase (A–G) as complete once all tasks in that group are done

---

## Dependencies

```
T001, T002, T003          (Phase 1 — no deps)
    ↓
T004, T005                (Phase 2 — use templates from Phase 1)
    ↓
T006–T011 [P]             (Group B — independent of each other, use T001 template)
T012–T014 [P]             (Group C — independent of each other; runtime depends on B outputs)
T015–T017 [P]             (Group D — independent of each other)
T018–T019 [P]             (Group E — independent of each other)
T020                      (Group F — independent, pure Python)
    ↓
T021                      (US2 — requires T006–T020 scripts to exist)
T022                      (US3 — requires T006–T020 scripts to have run and produced tables)
    ↓
T023–T026                 (Polish — run after all scripts exist)
```

**Parallel execution within Phase 3**:
- Groups B, C, D, E, F can all be worked on simultaneously (different directories, no file conflicts)
- Within each group, individual script conversions are fully parallelizable [P]

---

## Validation Checkpoints

| Gate | Condition |
|------|-----------|
| After Phase 1 | Templates exist and follow the plan.md structure |
| After each Group B–F script | `python src/scripts/<folder>/<script>.py` exits 0 (or gracefully if test data absent) |
| After T021 | `python run_pipeline.py --stage instagram` completes without error |
| After T022 | `python validate_outputs.py` exits 0 |
| After T023 | `ruff check .` reports 0 errors |
