# Feature Specification: Delta Lake MERGE Compliance

**Feature Branch**: `001-fix-delta-merge`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Corriger les violations Delta Lake MERGE : remplacer tous les appels `.mode('overwrite')` et `.parquet()` par des opérations `MERGE INTO` au format Delta dans les 4 notebooks violant la Principle IV (02_clusters/02_behavioral_clustering.ipynb, 02_clusters/03_fusion_visualization.ipynb, 03_memory_album/01_visual_embeddings.ipynb, 03_memory_album/02_scene_clustering.ipynb). Objectif : garantir l'idempotence des notebooks et l'intégrité des données du warehouse selon la constitution MyDigitalTwin."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fix Behavioral Clustering Notebook (Priority: P1)

Analytics Lead needs to update `src/scripts/02_clusters/02_behavioral_clustering.ipynb` to write warehouse tables using Delta MERGE INTO instead of `.mode("overwrite")`.

**Why this priority**: This notebook generates `beh_clusters_df` which populates critical warehouse tables. Using MERGE INTO ensures idempotency and prevents data loss on re-runs, aligning with the constitution's Principle IV.

**Independent Test**: Replace the single `.write.format("delta").mode("overwrite").save(out_path)` call with a proper Delta MERGE INTO operation. Verify the notebook can be re-run multiple times without corrupting previously written data.

**Acceptance Scenarios**:

1. **Given** the notebook is run a first time with fresh data, **When** the write operation completes, **Then** the Delta Lake table is created and populated with all records
2. **Given** the notebook is run a second time with the same input data, **When** the write operation completes, **Then** the table contains the same records without duplication (idempotent behavior)
3. **Given** the notebook is run with updated/modified input data, **When** the MERGE operation completes, **Then** matching records are updated and new records are inserted

---

### User Story 2 - Fix Fusion Visualization Notebook (Priority: P1)

Analytics Lead needs to update `src/scripts/02_clusters/03_fusion_visualization.ipynb` to replace both `.parquet()` and `.mode("overwrite")` operations with proper Delta MERGE INTO writes.

**Why this priority**: This notebook writes multiple tables (`interest_profiles`, and potentially others). The current code uses `.parquet()` instead of Delta format and `.mode("overwrite")`, which violates the warehouse-write policy and prevents proper merge semantics.

**Independent Test**: Identify all warehouse write operations in the notebook. Replace each `.mode("overwrite").parquet(out_path)` with a Delta MERGE INTO pattern that specifies a merge key for the table. Verify data integrity across multiple writes.

**Acceptance Scenarios**:

1. **Given** the `interest_profiles_df` is created with cluster metadata, **When** written to the warehouse, **Then** it uses Delta format with MERGE INTO semantics
2. **Given** the notebook contains multiple table writes, **When** any write occurs, **Then** all writes follow the same Delta MERGE pattern (not Parquet, not `.mode("overwrite")`)
3. **Given** the notebook re-runs with updated cluster information, **When** MERGE INTO executes, **Then** existing clusters are updated and new ones are inserted without overwriting the entire table

---

### User Story 3 - Fix Visual Embeddings Notebook (Priority: P1)

Analytics Lead needs to update `src/scripts/03_memory_album/01_visual_embeddings.ipynb` to replace `.mode('overwrite')` with proper Delta MERGE INTO semantics.

**Why this priority**: This notebook generates visual embeddings for the memory album feature. Using MERGE INTO instead of overwrite ensures that re-running the notebook for new photos doesn't delete existing embedding data.

**Independent Test**: Locate all `.mode('overwrite')` calls in the notebook. Replace each with a Delta MERGE INTO operation that identifies the merge key (e.g., image ID or hash). Verify the notebook can process new images without deleting prior embeddings.

**Acceptance Scenarios**:

1. **Given** the notebook processes a batch of images and creates embeddings, **When** written to the warehouse, **Then** uses Delta MERGE INTO with a stable merge key (e.g., image_id)
2. **Given** the notebook is re-run with additional new images, **When** MERGE INTO executes, **Then** new embeddings are inserted and existing ones remain unchanged
3. **Given** an existing embedding is updated (e.g., model improved), **When** MERGE matches on the key, **Then** the record is updated in-place without table recreation

---

### User Story 4 - Fix Scene Clustering Notebook (Priority: P1)

Analytics Lead needs to update `src/scripts/03_memory_album/02_scene_clustering.ipynb` to replace all `.mode('overwrite')` calls with proper Delta MERGE INTO operations.

**Why this priority**: This notebook performs scene clustering on visual data. Multiple overwrite operations can lead to inconsistent state if the notebook fails mid-run. MERGE INTO provides atomicity and idempotency.

**Independent Test**: Identify all `.mode('overwrite')` calls (expected to be multiple). Replace each with a Delta MERGE INTO operation specifying the appropriate merge key for each table. Verify all write operations follow the same pattern.

**Acceptance Scenarios**:

1. **Given** the notebook performs multiple transformations and writes multiple tables, **When** all write operations are executed, **Then** each uses Delta MERGE INTO (no Parquet, no overwrite mode)
2. **Given** one of the write operations fails mid-execution, **When** the notebook is re-run, **Then** prior successful writes are not overwritten and merge operations are replayed correctly
3. **Given** clustering parameters are tuned and the notebook re-runs, **When** MERGE executes for each table, **Then** all tables reach a consistent final state matching the new parameters

---

### Edge Cases

- What happens when a merge key is not uniquely identifying records in a table? → Merge will fail; notebook must define explicit key(s)
- How should the notebook handle schema evolution (new columns added to tables)? → Delta MERGE INTO will handle schema-on-write gracefully; any new columns should be documented
- What if the first run creates the table without Delta format? → The fix must ensure initial create also uses Delta format and mode
- How should timestamps and modified dates be updated in MERGE operations? → Include `WHEN MATCHED` clause to update modification timestamps

## Data Engineering Context *(mandatory for ingestion/analytics features)*

### Notebook Artifacts

Four analytical notebooks in `src/scripts/` require Delta Lake MERGE corrections:

1. `src/scripts/02_clusters/02_behavioral_clustering.ipynb`
   - **Current output**: `data/warehouse/[table_name]`
   - **Current violation**: `.write.format("delta").mode("overwrite").save(out_path)`
   - **Key table**: `beh_clusters_df` → warehouse table (name to be identified)

2. `src/scripts/02_clusters/03_fusion_visualization.ipynb`
   - **Current output**: `data/warehouse/interest_profiles`, potentially others
   - **Current violation**: `.write.mode("overwrite").parquet(out_path)` and `.write.mode("overwrite")`
   - **Key table**: `interest_profiles` with cluster metadata

3. `src/scripts/03_memory_album/01_visual_embeddings.ipynb`
   - **Current output**: `data/warehouse/[embedding_table]`
   - **Current violation**: `.mode('overwrite')` on embedding writes
   - **Key table**: Visual embeddings keyed by image ID or similar

4. `src/scripts/03_memory_album/02_scene_clustering.ipynb`
   - **Current output**: Multiple warehouse tables for scene data
   - **Current violation**: Multiple `.mode('overwrite')` calls
   - **Key table**: Scene cluster data and metadata

### Warehouse Schema & Merge Keys

Each notebook's table write must specify:

- **Table name**: Explicit table path in `data/warehouse/`
- **Format**: Delta Lake (`.format("delta")`)
- **Merge key**: Column(s) uniquely identifying records (e.g., `image_id`, `cluster_id`, `scene_id`)
- **MERGE operation**: Use Delta's `MERGE INTO target USING source ON key WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *`
- **Initial write**: Use `.mode("overwrite")` only on first creation; subsequent runs use MERGE
- **Idempotency**: Notebook must be re-runable without data loss or duplication

### Data Quality & Validation

- **No schema validation required** beyond Delta's standard schema-on-write
- **Assumption**: Upstream data in `data/processed/` is already validated by Ingestion Lead
- **Downstream consumer**: Dashboard reads from these warehouse tables; MERGE consistency ensures clean reads
- **Test strategy**: Re-run each notebook twice; verify row counts and data consistency before/after second run

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Notebook MUST replace all `.write.mode("overwrite")` calls with Delta `MERGE INTO` semantics
- **FR-002**: Notebook MUST use `.format("delta")` for all warehouse writes (not `.parquet()`)
- **FR-003**: Each warehouse table MUST have an explicitly defined merge key (documented in notebook cell)
- **FR-004**: MERGE operation MUST include `WHEN MATCHED THEN UPDATE SET *` and `WHEN NOT MATCHED THEN INSERT *` clauses
- **FR-005**: Initial table creation MAY use `.mode("overwrite")` to bootstrap, but subsequent runs MUST use MERGE INTO
- **FR-006**: Notebook MUST be idempotent (re-running with same input produces same output without data loss)
- **FR-007**: Notebook MUST document merge key and MERGE strategy in a markdown cell for maintainability

### Key Entities

- **Behavioral Cluster**: Grouping of user interests and platform engagement patterns; identified by unique cluster ID
- **Interest Profile**: Summary of a cluster with keywords, samples, and platform distribution; identified by cluster ID
- **Visual Embedding**: ML embedding vector for an image; identified by image ID or content hash
- **Scene Cluster**: Grouping of images by detected scene (indoor/outdoor, time of day, etc.); identified by scene ID or record ID

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 4 notebooks execute without `.mode("overwrite")` errors or Parquet fallbacks (0 violations in final code)
- **SC-002**: Each notebook can be re-run 5 consecutive times with the same input; final table state is identical on run 1 and run 5 (idempotency verified)
- **SC-003**: All warehouse tables are in Delta Lake format; running `DESCRIBE FORMATTED [table_name]` shows `Type: DELTA` (100% Delta compliance)
- **SC-004**: MERGE operations complete without duplicate key errors or schema mismatches (0 runtime failures when re-running)
- **SC-005**: Notebooks execute successfully with data validation on output (verify row counts, null checks, data ranges remain valid after MERGE)

---

## Assumptions

- **Merge keys are stable**: Each notebook already produces data with unique, non-changing merge keys (e.g., cluster_id, image_id). If unclear, this will be clarified during implementation.
- **Initial tables may be recreated**: The first run may use `.mode("overwrite")` to bootstrap Delta tables; only subsequent runs require MERGE.
- **Spark session available**: Each notebook inherits a Spark session from `config.py` via `build_spark_session()`; no modifications to session creation needed.
- **Input data schema unchanged**: Data written to `data/processed/` by Ingestion Lead maintains consistent schema; notebooks do not need to handle schema drift.
- **No cross-notebook dependencies**: Each notebook's fix is independent; fixing one does not require changes to another (though all follow the same MERGE pattern).
- **Delta Lake available**: Spark environment already has Delta Lake 3.x installed (verified in `Dockerfile`).
