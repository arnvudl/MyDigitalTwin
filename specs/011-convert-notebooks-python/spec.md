# Feature Specification: Convert Analytical Notebooks to Production Python Scripts

**Feature Branch**: `011-convert-notebooks-python`

**Created**: 2026-05-13

**Status**: Draft

**Input**: User description: "Convertir les notebooks Jupyter analytiques en scripts Python de production dans le projet MyDigitalTwin (Spark + Delta Lake)."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Single Analytical Script (Priority: P1)

A developer or data engineer wants to run one specific analytical stage (e.g., Instagram exploration, content clustering) independently, without executing the entire pipeline.

**Why this priority**: This is the most common workflow during development, debugging, and incremental updates. Running a single script validates one conversion at a time and is the core requirement.

**Independent Test**: Can be fully tested by running `python src/scripts/01_exploration/instagram.py` and verifying the expected Delta/Parquet output exists with correct schema and row count.

**Acceptance Scenarios**:

1. **Given** a converted script exists at its expected path, **When** the user runs `python src/scripts/<folder>/<script>.py`, **Then** the script completes without errors, writes the expected output table, and exits cleanly (no hanging Spark session).
2. **Given** the Docker Spark environment has limited RAM, **When** the script runs, **Then** memory usage stays within configured limits and no OOM errors occur.
3. **Given** a script finishes execution, **When** it exits, **Then** the Spark session is stopped and all DataFrames are unpersisted.

---

### User Story 2 - Run the Full Pipeline End-to-End (Priority: P2)

A developer wants to execute all analytical stages in the correct order (01 → 07) in a single command, without manually chaining scripts.

**Why this priority**: Needed for CI/CD, full pipeline validation, and production deployment runs.

**Independent Test**: Can be fully tested by running `python run_pipeline.py` and verifying all expected output tables are present and valid after completion.

**Acceptance Scenarios**:

1. **Given** all converted scripts exist, **When** the user runs `python run_pipeline.py`, **Then** all stages execute sequentially in order (01 → 07), respecting existing `.py` scripts already in the pipeline.
2. **Given** one stage fails, **When** the pipeline runs, **Then** a clear error message identifies the failing stage and the pipeline stops at that point.
3. **Given** the pipeline completes, **When** the user inspects outputs, **Then** all expected Delta tables exist with correct schemas.

---

### User Story 3 - Validate Conversion Correctness at Build Time (Priority: P3)

After converting notebooks to Python scripts, a developer wants to verify the outputs match what the notebooks previously produced — schema, row counts, and column names.

**Why this priority**: Ensures the conversion did not silently break any analytical logic. This is a smoke test that runs as part of the build/verification step.

**Independent Test**: Can be fully tested by running `python validate_outputs.py` and checking that all tables pass schema, row count, and column name assertions.

**Acceptance Scenarios**:

1. **Given** a script has been executed, **When** the validation script runs, **Then** it checks each output table's schema, row count, and column names against reference expectations.
2. **Given** an output table has wrong schema or unexpected row count, **When** the validation runs, **Then** it reports the specific table and the mismatch (expected vs actual).
3. **Given** all outputs match expectations, **When** the validation runs, **Then** it exits with code 0 (success) suitable for CI integration.

---

### Edge Cases

- What happens if a notebook contained only visualizations and no data output? → The converted script produces no output; the validation script skips it.
- What happens if a Delta table does not exist yet when validation runs? → Validation reports the table as missing and fails with a clear message.
- What happens if the Docker Spark container runs out of memory mid-script? → The Spark session fails with an OOM error; the script surfaces this without hanging.
- How does the system handle scripts that depend on outputs from a previous stage? → `run_pipeline.py` enforces sequential execution; individual scripts may fail gracefully if upstream outputs are missing.

---

## Data Engineering Context *(mandatory for ingestion/analytics features)*

### Scope of Conversion

| Source Notebook | Target Script | Stage |
|---|---|---|
| `01_exploration/instagram.ipynb` | `01_exploration/instagram.py` | Exploration |
| `01_exploration/google_youtube.ipynb` | `01_exploration/google_youtube.py` | Exploration |
| `01_exploration/spotify.ipynb` | `01_exploration/spotify.py` | Exploration |
| `01_exploration/tiktok.ipynb` | `01_exploration/tiktok.py` | Exploration |
| `01_exploration/twitter.ipynb` | `01_exploration/twitter.py` | Exploration |
| `01_exploration/netflix.ipynb` | `01_exploration/netflix.py` | Exploration |
| `02_clusters/01_content_clustering.ipynb` | `02_clusters/01_content_clustering.py` | Clustering |
| `02_clusters/02_behavioral_clustering.ipynb` | `02_clusters/02_behavioral_clustering.py` | Clustering |
| `02_clusters/03_fusion_visualization.ipynb` | `02_clusters/03_fusion_visualization.py` | Clustering |
| `03_memory_album/01_visual_embeddings.ipynb` | `03_memory_album/01_visual_embeddings.py` | Memory Album |
| `03_memory_album/02_scene_clustering.ipynb` | `03_memory_album/02_scene_clustering.py` | Memory Album |
| `03_memory_album/03_music_matching.ipynb` | `03_memory_album/03_music_matching.py` | Memory Album |
| `05_CLIP/01_clip_embeddings.ipynb` | `05_CLIP/01_clip_embeddings.py` | CLIP |
| `05_CLIP/02_clip_clustering.ipynb` | `05_CLIP/02_clip_clustering.py` | CLIP |
| `06_social/01_social_graph.ipynb` | `06_social/01_social_graph.py` | Social Graph |

### Scripts to Preserve Untouched

- `src/scripts/03_memory_album/scripts/*.py` — existing production scripts
- `src/scripts/04_clone/*.py` — existing production scripts
- `src/scripts/05_CLIP/00_collect_photos.py` — existing production script
- `src/scripts/07_psy/01_build_dossier.py` — existing production script

### Spark Session Management

- Chaque script reproduit fidèlement les paramètres `build_spark_session()` du notebook source (app_name, driver_memory, snappy, delta) — aucune valeur normalisée imposée.
- `google_youtube.py` utilise `driver_memory="6g"` (dataset YouTube volumineux).
- `03_memory_album/01_visual_embeddings.py` utilise `driver_memory="4g"`, `snappy=True`, `delta=True`.
- `06_social/01_social_graph.py` n'utilise **pas Spark** — traitement pure Python/JSON séquentiel (~100 nœuds max).
- Chaque script Spark appelle `spark.stop()` en fin d'exécution via `try/finally`.
- `.cache()` est conservé dans `05_CLIP/02_clip_clustering.py` (usage légitime du notebook source).
- `.collect()` n'est jamais appelé sur de gros datasets.

### Data Quality & Validation

- A `validate_outputs.py` script checks each output table post-conversion.
- Checks: schema (column names + types), row count (non-zero, within expected range), presence of key columns.
- Designed to run once at build/verification time, not as a continuous test suite.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each notebook MUST be converted to a standalone `.py` script at the same path within `src/scripts/`, preserving the analytical logic.
- **FR-002**: All visualizations (matplotlib, plotly inline) MUST be removed from converted scripts.
- **FR-003**: All file paths MUST be imported from `config.py`; no hardcoded paths are permitted.
- **FR-004**: Each script MUST initialize a Spark session with explicit memory configuration and stop it on exit.
- **FR-005**: Each script MUST unpersist DataFrames after use and avoid unnecessary `.cache()` or `.collect()` calls on large datasets.
- **FR-006**: Each script MUST be executable independently via `python <script_path>`.
- **FR-007**: A `run_pipeline.py` entry point MUST execute all scripts in pipeline order (01 → 07), skipping stages that are already `.py` files not derived from notebooks.
- **FR-008**: The `run_pipeline.py` MUST allow running individual stages by name or index, in addition to full pipeline execution.
- **FR-009**: A `validate_outputs.py` script MUST verify schema, row counts, and column presence for each converted script's output table.
- **FR-010**: Existing `.py` scripts (04_clone, 07_psy, 05_CLIP/00_collect_photos, 03_memory_album/scripts/) MUST NOT be modified.

### Key Entities

- **Converted Script**: A `.py` file derived from a notebook, containing the same analytical logic, without visualizations, with managed Spark session lifecycle.
- **Pipeline Entry Point**: `run_pipeline.py` — orchestrates sequential or selective execution of all stages.
- **Validation Script**: `validate_outputs.py` — smoke-tests all output tables after conversion or pipeline run.
- **Spark Session**: Created per script with Docker-optimized memory settings; always stopped on exit.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 15 notebooks are converted to `.py` scripts and each can be executed independently without errors.
- **SC-002**: The full pipeline runs end-to-end via a single command without manual intervention.
- **SC-003**: No Spark session remains open after a script exits (verified by absence of running Spark processes).
- **SC-004**: The validation script confirms all output tables match expected schema, column names, and non-zero row counts for each converted script.
- **SC-005**: No existing `.py` scripts are modified during the conversion.
- **SC-006**: All converted scripts complete execution within the same time bounds as their notebook equivalents, without triggering out-of-memory errors in the Docker Spark environment.

---

## Assumptions

- The Docker Spark environment has a fixed, limited amount of RAM; scripts must fit within that constraint without tuning at runtime.
- Notebooks are assumed to produce deterministic outputs (same data in → same schema and approximate row count out); the validation script uses this assumption.
- Visualizations in notebooks are considered non-functional for production and are dropped entirely; no image export is required.
- The `04_clone/` and `07_psy/` stages are already in production `.py` format and are integrated into `run_pipeline.py` as-is.
- `config.py` already exposes all necessary paths; no new path variables need to be added as part of this feature (may be revisited per notebook).
- The conversion preserves analytical logic faithfully; no algorithmic changes are introduced.
