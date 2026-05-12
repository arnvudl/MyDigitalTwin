# Research: Delta Lake MERGE INTO Pattern Design

**Purpose**: Identify all warehouse write violations and design consistent MERGE patterns  
**Date**: 2026-05-12  
**Scope**: 4 notebooks with Constitution Principle IV violations

---

## Findings Summary

### Notebook 1: `src/scripts/02_clusters/02_behavioral_clustering.ipynb`

**Current violation**:
```python
beh_clusters_df.write.format("delta").mode("overwrite").save(out_path)
```

**What gets written**: Behavioral cluster data frame with cluster ID and metadata

**Merge key candidates**:
- `cluster_id` (primary) — uniquely identifies each cluster
- Assumption: cluster IDs are stable and recomputed identically on re-runs

**MERGE pattern**: Single table write with cluster_id as merge key
```python
# Pseudo-code
MERGE INTO warehouse.beh_clusters target
USING beh_clusters_df source
ON target.cluster_id = source.cluster_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

**Rationale**: Cluster IDs are derived from user engagement patterns. On re-run, same patterns produce same cluster IDs. MERGE ensures prior cluster metadata isn't lost and new clusters are added.

---

### Notebook 2: `src/scripts/02_clusters/03_fusion_visualization.ipynb`

**Current violations** (multiple):
```python
# Violation 1: Parquet + overwrite mode
interest_profiles_df.write.mode("overwrite").parquet(out_path)

# Violation 2: Potential other writes
df.write.mode("overwrite")...
```

**What gets written**: 
- `interest_profiles`: Cluster summaries with keywords, samples, platform distribution
- Potentially other summary tables

**Merge key candidates for `interest_profiles`**:
- `cluster_id` (primary) — each cluster has one profile
- Stable across runs since cluster IDs are stable

**MERGE pattern**: Delta (not Parquet) with cluster_id merge key
```python
# Fix pattern
interest_profiles_df.write.format("delta").mode("overwrite").save(out_path)  # Initial create
# On re-run:
spark.sql(f"""
  MERGE INTO {table_name} target
  USING interest_profiles_df source
  ON target.cluster_id = source.cluster_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")
```

**Rationale**: Replace `.parquet()` with `.format("delta")` AND replace `.mode("overwrite")` with MERGE. Profiles may have updated keywords/samples; MERGE ensures prior data isn't lost.

---

### Notebook 3: `src/scripts/03_memory_album/01_visual_embeddings.ipynb`

**Current violation**:
```python
embeddings_df.write.mode('overwrite')...
```

**What gets written**: Visual embedding vectors for images (ML embeddings from CLIP or similar)

**Merge key candidates**:
- `image_id` or `image_hash` — uniquely identifies each image
- Assumption: Image IDs/hashes remain stable

**MERGE pattern**: With image_id/hash merge key
```python
# Fix pattern
spark.sql(f"""
  MERGE INTO {warehouse_table} target
  USING embeddings_df source
  ON target.image_id = source.image_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")
```

**Rationale**: New photos are added to dataset over time. MERGE ensures prior embeddings are preserved; new photos get new embeddings. Model improvements can re-compute embeddings; MERGE updates matching records.

---

### Notebook 4: `src/scripts/03_memory_album/02_scene_clustering.ipynb`

**Current violations** (multiple):
```python
# Multiple .mode('overwrite') calls
some_df.write.mode('overwrite')...
scene_clusters_df.write.mode('overwrite')...
```

**What gets written**: 
- Scene clusters (image groupings by detected scene)
- Multiple associated tables (cluster metadata, sample images, etc.)

**Merge key strategy per table**:
- Primary scene cluster table: `scene_id` or `record_id`
- Associated metadata tables: Foreign key linking back to scene_id

**MERGE pattern**: Consistent pattern for all writes
```python
# Pattern 1: Main scene cluster table
spark.sql(f"""
  MERGE INTO {warehouse}/scene_clusters target
  USING scene_clusters_df source
  ON target.scene_id = source.scene_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")

# Pattern 2: Associated metadata table
spark.sql(f"""
  MERGE INTO {warehouse}/scene_samples target
  USING scene_samples_df source
  ON target.scene_id = source.scene_id AND target.sample_index = source.sample_index
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")
```

**Rationale**: Scene clustering may re-compute on re-runs or with new images. MERGE ensures consistency across multiple related tables and prevents accidental data loss.

---

## Merge Key Validation Strategy

For each notebook, before implementation:

1. **Identify merge key(s)** — What uniquely identifies a record?
   - Cluster IDs, Image IDs, Scene IDs, etc.
   
2. **Verify stability** — Do merge keys remain constant on re-runs?
   - Check: Does `cluster_id` get recomputed the same way each time?
   - Assumption: Yes, because they're deterministic (based on user engagement patterns or image content)

3. **Check uniqueness** — Is the merge key(s) unique within the table?
   - Check: Can a cluster_id appear twice in beh_clusters_df? No, by design.
   - Assumption: Yes, merge keys are unique

4. **Plan for edge cases** — What if a record's merge key changes?
   - Assumption: They don't (cluster IDs are stable, image IDs are stable)
   - If they do, document as "data quality issue" to be fixed separately

---

## Initial Table Creation vs. Incremental Updates

### Strategy: Hybrid approach

**First run** (table doesn't exist yet):
- Use `.mode("overwrite")` to bootstrap Delta table: `df.write.format("delta").mode("overwrite").save(path)`
- This creates the table with initial data

**Subsequent runs** (table exists):
- Use `MERGE INTO` to idempotently update: prevents re-creating table, preserves prior data

### Implementation detail:
Many notebooks won't distinguish between first-run and subsequent runs. Instead:
- Option A: Always use `.mode("overwrite")` on first run, MERGE on subsequent
- Option B: Always use MERGE; handle "table doesn't exist" exception with fallback to create

**Recommendation**: Option A (clearer code) or use Delta's automatic handling (Option B via `MERGE` only, Delta creates table if missing)

---

## Spark SQL vs. PySpark DataFrame API

### For implementing MERGE:

**Spark SQL** (recommended):
```python
spark.sql(f"""
  MERGE INTO {table_name} target
  USING temp_source source
  ON target.cluster_id = source.cluster_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")
```

**PySpark DataFrame API** (limited support):
- Delta Lake's PySpark API doesn't have direct `MERGE` syntax
- Would require writing temp table, then using SQL

**Recommendation**: Use Spark SQL for all MERGE operations. Notebooks already use SQL for complex queries.

---

## Schema-on-write Behavior

**Current state**: All notebooks already use Delta tables (implicit or explicit)  
**Behavior**: Delta automatically handles schema evolution (new columns added)

**For MERGE operations**:
- If source DF has new columns, Delta adds them to target table
- If target has columns source doesn't have, they're preserved (if schema is set explicitly) or nulled
- Risk: Unintended schema changes

**Mitigation**:
- Document expected schema in markdown cell per notebook
- Use `WHEN MATCHED THEN UPDATE SET *` (updates all columns from source)
- Consider explicit `UPDATE SET target.col1 = source.col1, ...` if fine-grained control needed

---

## Summary: Consistent Pattern for All 4 Notebooks

All 4 notebooks will follow this pattern:

```python
from pyspark.sql import functions as F
import os
from config import WAREHOUSE

# ... upstream transformations ...

# Merge key for this table (document in markdown cell above)
MERGE_KEY_COLS = ["cluster_id"]  # or ["image_id"], ["scene_id"], etc.

# Option 1: DataFrame API + Spark SQL (recommended)
output_df.write.format("delta").mode("overwrite").save(os.path.join(WAREHOUSE, "table_name"))  # First run

# Subsequent runs: use MERGE (comment out first-run line)
merge_key_condition = " AND ".join([f"target.{col} = source.{col}" for col in MERGE_KEY_COLS])
spark.sql(f"""
  MERGE INTO {os.path.join(WAREHOUSE, "table_name").replace(os.sep, "/")} target
  USING output_df source
  ON {merge_key_condition}
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")
```

**Consistency benefits**:
- All notebooks follow same pattern
- Easy to code-review
- Easy to maintain
- Idempotent across all 4 notebooks

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Merge key changes between runs (data corruption) | Document merge key strategy in markdown; validate before run |
| Schema mismatch (new columns in source DF) | Delta auto-handles; document expected schema |
| MERGE operation fails mid-table | Delta ensures atomicity; failure leaves table unchanged |
| Performance degradation on large tables | Partition keys (future optimization, not in this fix) |
| Confusion between "first run" and "subsequent runs" | Document clearly in notebook; consider auto-detection or config flag |

---

**Conclusion**: All 4 notebooks can be fixed using a consistent Delta MERGE pattern with explicitly documented merge keys. No major risks; mitigations are standard Delta practices.
