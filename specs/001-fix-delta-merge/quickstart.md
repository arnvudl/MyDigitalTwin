# Quickstart: Delta Lake MERGE INTO Patterns

**Purpose**: Copy-paste templates for fixing each notebook  
**Date**: 2026-05-12  
**Audience**: Analytics Lead implementing the fix

---

## Template 1: Simple Single-Table MERGE

**Use case**: Notebook 02_behavioral_clustering  
**Pattern**: One DataFrame → one warehouse table with cluster_id merge key

### Before (❌ Violation)
```python
# Current code (violates Constitution Principle IV)
from config import WAREHOUSE
import os

beh_clusters_df.write.format("delta").mode("overwrite").save(os.path.join(WAREHOUSE, "beh_clusters"))
```

### After (✅ Fixed)
```python
from config import WAREHOUSE
import os

# ── Merge key definition ────────────────────────────────────────────
# Merge key: cluster_id (uniquely identifies each behavioral cluster)
# This key is recomputed deterministically on each run based on user engagement patterns.

table_path = os.path.join(WAREHOUSE, "beh_clusters")
merge_key = "cluster_id"

# Option A: First run (bootstrap table)
beh_clusters_df.write.format("delta").mode("overwrite").save(table_path)

# Option B: Subsequent runs (idempotent MERGE)
spark.sql(f"""
  MERGE INTO {table_path.replace(os.sep, "/")} target
  USING beh_clusters_df source
  ON target.{merge_key} = source.{merge_key}
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")

# ✅ Result: Idempotent. Re-running doesn't create duplicates or lose data.
```

---

## Template 2: Parquet → Delta with MERGE

**Use case**: Notebook 03_fusion_visualization (interest_profiles)  
**Pattern**: Replace `.parquet()` with `.format("delta")` AND replace `.mode("overwrite")` with MERGE

### Before (❌ Violation)
```python
from config import WAREHOUSE
import os

out_path = os.path.join(WAREHOUSE, "interest_profiles")

# Violation 1: Using .parquet() instead of .format("delta")
# Violation 2: Using .mode("overwrite") instead of MERGE
interest_profiles_df.write.mode("overwrite").parquet(out_path)
```

### After (✅ Fixed)
```python
from config import WAREHOUSE
import os
from pyspark.sql import functions as F

# ── Merge key definition ────────────────────────────────────────────
# Merge key: cluster_id (one profile per cluster)
# Profiles are updated when cluster keywords or samples are refined.

out_path = os.path.join(WAREHOUSE, "interest_profiles")
table_path = out_path.replace(os.sep, "/")  # Spark SQL requires forward slashes
merge_key = "cluster_id"

# Option A: First run (bootstrap)
interest_profiles_df.write.format("delta").mode("overwrite").save(out_path)

# Option B: Subsequent runs (idempotent MERGE)
spark.sql(f"""
  MERGE INTO {table_path} target
  USING interest_profiles_df source
  ON target.{merge_key} = source.{merge_key}
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")

# ✅ Result: Uses Delta format (not Parquet); idempotent re-runs.
```

---

## Template 3: Multiple MERGE Operations (Same Notebook)

**Use case**: Notebook 03_fusion_visualization (if multiple tables)  
**Pattern**: Apply same MERGE to each table independently

### Before (❌ Violation)
```python
from config import WAREHOUSE
import os

table1_df.write.mode("overwrite").parquet(os.path.join(WAREHOUSE, "table1"))
table2_df.write.mode("overwrite").parquet(os.path.join(WAREHOUSE, "table2"))
```

### After (✅ Fixed)
```python
from config import WAREHOUSE
import os

# ── Table 1: interest_profiles ──────────────────────────────────────
table1_path = os.path.join(WAREHOUSE, "interest_profiles").replace(os.sep, "/")
table1_key = "cluster_id"

spark.sql(f"""
  MERGE INTO {table1_path} target
  USING table1_df source
  ON target.{table1_key} = source.{table1_key}
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")

# ── Table 2: (other table) ────────────────────────────────────────
table2_path = os.path.join(WAREHOUSE, "table2").replace(os.sep, "/")
table2_key = "cluster_id"

spark.sql(f"""
  MERGE INTO {table2_path} target
  USING table2_df source
  ON target.{table2_key} = source.{table2_key}
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")

# ✅ Result: Both tables use Delta + MERGE; both are idempotent.
```

---

## Template 4: Embedding Table with Model Tracking

**Use case**: Notebook 01_visual_embeddings  
**Pattern**: Single table with embedding vectors; track model version

### Before (❌ Violation)
```python
from config import WAREHOUSE
import os

embeddings_df.write.mode('overwrite').save(os.path.join(WAREHOUSE, "visual_embeddings"))
```

### After (✅ Fixed)
```python
from config import WAREHOUSE
import os
from pyspark.sql import functions as F
from datetime import datetime

# ── Merge key definition ────────────────────────────────────────────
# Merge key: image_id (uniquely identifies each image)
# Embeddings may be re-computed with improved model versions.

table_path = os.path.join(WAREHOUSE, "visual_embeddings").replace(os.sep, "/")
merge_key = "image_id"
model_version = "CLIP-v1"  # Document embedding model version
timestamp = F.current_timestamp()

# Add metadata columns if not already present
embeddings_with_meta = embeddings_df.withColumn("model_version", F.lit(model_version)) \
                                     .withColumn("updated_date", timestamp)

# Option A: First run
embeddings_with_meta.write.format("delta").mode("overwrite").save(os.path.join(WAREHOUSE, "visual_embeddings"))

# Option B: Subsequent runs
spark.sql(f"""
  MERGE INTO {table_path} target
  USING embeddings_with_meta source
  ON target.{merge_key} = source.{merge_key}
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")

# ✅ Result: Embeddings updated when model improves; new images added; idempotent.
```

---

## Template 5: Composite Merge Key (Multiple Columns)

**Use case**: Notebook 02_scene_clustering (scene_samples table)  
**Pattern**: Merge key combines multiple columns (scene_id + sample_index)

### Before (❌ Violation)
```python
from config import WAREHOUSE
import os

scene_samples_df.write.mode('overwrite').save(os.path.join(WAREHOUSE, "scene_samples"))
```

### After (✅ Fixed)
```python
from config import WAREHOUSE
import os

# ── Merge key definition ────────────────────────────────────────────
# Merge key: (scene_id, sample_index) — composite key
# Uniquely identifies each sample within each scene cluster.

table_path = os.path.join(WAREHOUSE, "scene_samples").replace(os.sep, "/")
merge_key_cols = ["scene_id", "sample_index"]

# Construct merge condition (AND all key columns)
merge_condition = " AND ".join([f"target.{col} = source.{col}" for col in merge_key_cols])

# Option A: First run
scene_samples_df.write.format("delta").mode("overwrite").save(os.path.join(WAREHOUSE, "scene_samples"))

# Option B: Subsequent runs
spark.sql(f"""
  MERGE INTO {table_path} target
  USING scene_samples_df source
  ON {merge_condition}
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")

# ✅ Result: Composite key ensures uniqueness; idempotent re-runs.
```

---

## Template 6: Explicit Column Mapping (Fine-Grained Control)

**Use case**: Any notebook where you want to explicitly control which columns update  
**Pattern**: Use explicit column list instead of `UPDATE SET *`

### Pattern
```python
from config import WAREHOUSE
import os
from pyspark.sql import functions as F

table_path = os.path.join(WAREHOUSE, "table_name").replace(os.sep, "/")
merge_key = "key_col"

spark.sql(f"""
  MERGE INTO {table_path} target
  USING source_df source
  ON target.{merge_key} = source.{merge_key}
  WHEN MATCHED THEN UPDATE SET 
    target.col1 = source.col1,
    target.col2 = source.col2,
    target.updated_date = current_timestamp()
  WHEN NOT MATCHED THEN INSERT (key_col, col1, col2, created_date, updated_date)
    VALUES (source.key_col, source.col1, source.col2, current_timestamp(), current_timestamp())
""")

# ✅ Result: Only specified columns update; timestamp automatically updated.
```

---

## Implementation Checklist

For each notebook, follow this checklist:

- [ ] **Identify merge key(s)** — What uniquely identifies a record?
  - Document in markdown cell above the write operation
  
- [ ] **Check merge key stability** — Does it remain constant on re-runs?
  - Confirm: cluster_id, image_id, scene_id are all stable
  
- [ ] **Check merge key uniqueness** — Can the key appear multiple times?
  - Confirm: Each key identifies exactly one record
  
- [ ] **Choose MERGE pattern** — Use appropriate template above
  - Single key: Template 1
  - Multiple tables: Template 3
  - Composite key: Template 5
  - Fine-grained control: Template 6
  
- [ ] **Replace all `.mode("overwrite")` and `.parquet()`**
  - Use `.format("delta")` for format
  - Use `spark.sql(MERGE INTO ...)` for write
  
- [ ] **Test idempotency** — Run notebook twice, verify final state identical
  - Run 1: Baseline
  - Run 2: Should produce same row counts, same values
  
- [ ] **Run linting** — `ruff check .` must pass
  - Fix any E9, F63, F7, F82 errors

- [ ] **Run data quality tests** — `pytest tests/data_quality/ -v`
  - All tests must pass
  
- [ ] **Verify Delta format** — `DESCRIBE FORMATTED table_name` shows `Type: DELTA`
  - All warehouse tables must be Delta, not Parquet

---

## Common Pitfalls

### ❌ Pitfall 1: Forgetting `.replace(os.sep, "/")`
```python
# WRONG (on Windows, backslashes break Spark SQL path)
spark.sql(f"MERGE INTO {table_path} ...")

# CORRECT
table_path = os.path.join(WAREHOUSE, "table").replace(os.sep, "/")
spark.sql(f"MERGE INTO {table_path} ...")
```

### ❌ Pitfall 2: Using wrong merge key
```python
# WRONG (row_number() changes on every run)
spark.sql("""
  MERGE INTO target
  USING source
  ON target.row_number = source.row_number  -- UNSTABLE
  WHEN MATCHED THEN UPDATE SET *
""")

# CORRECT (use stable unique identifier)
spark.sql("""
  MERGE INTO target
  USING source
  ON target.cluster_id = source.cluster_id  -- STABLE & UNIQUE
  WHEN MATCHED THEN UPDATE SET *
""")
```

### ❌ Pitfall 3: Forgetting first-run bootstrap
```python
# WRONG (MERGE fails if table doesn't exist)
spark.sql("MERGE INTO warehouse.table ...")  -- Table doesn't exist yet!

# CORRECT (create first, then merge)
df.write.format("delta").mode("overwrite").save(path)  # First run
# Then on subsequent runs:
spark.sql("MERGE INTO ...")  -- Table exists, merge works
```

### ❌ Pitfall 4: Using INSERT/OVERWRITE instead of MERGE
```python
# WRONG (recreates table, loses prior data)
df.write.format("delta").mode("overwrite").save(path)  -- EVERY run

# CORRECT (uses MERGE on subsequent runs)
# Run 1: .mode("overwrite")
# Run 2+: MERGE INTO
```

---

## Testing Your Fix

### Manual test (after implementing):

```bash
# 1. Run the notebook once (creates table)
jupyter notebook src/scripts/02_clusters/02_behavioral_clustering.ipynb
# ... execute all cells ...

# 2. Check table exists and is Delta
spark-shell
> spark.sql("DESCRIBE FORMATTED warehouse.beh_clusters").show()
# Should show: Type: DELTA

# 3. Run notebook again (tests MERGE idempotency)
jupyter notebook src/scripts/02_clusters/02_behavioral_clustering.ipynb
# ... execute all cells again ...

# 4. Verify same data
spark-shell
> val count1 = spark.sql("SELECT COUNT(*) FROM warehouse.beh_clusters").collect()(0)(0)
> println(s"Row count: $count1")
# Should be same on both runs
```

### Automated test (via pytest):

```bash
# Run data quality tests (they'll validate output)
pytest tests/data_quality/ -v

# Run linting
ruff check .
```

---

## Questions?

- **Q**: What if the merge key has nulls?  
  **A**: MERGE requires non-null keys. Filter them out before merge, or handle as separate logic.

- **Q**: What if the merge key changes between runs?  
  **A**: Data quality issue. This suggests non-deterministic logic. Debug upstream transformations.

- **Q**: Can I use MERGE on a table without a proper key?  
  **A**: No. Every MERGE operation requires an explicit, unique, stable merge key. Define one first.

- **Q**: Do I need indexes?  
  **A**: No. Delta handles optimization. Future performance tuning can add partition keys if needed.

- **Q**: What if I need to delete old records?  
  **A**: Use `WHEN MATCHED AND source.is_deleted THEN DELETE` clause (future enhancement, not in this fix).

---

**Conclusion**: Use these templates to implement MERGE INTO across all 4 notebooks. Each template handles a specific pattern; adapt as needed for your table structure.
