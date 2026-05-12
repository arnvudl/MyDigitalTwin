# Data Model: Delta Lake MERGE Operations

**Purpose**: Define entities, attributes, and merge keys for warehouse tables  
**Date**: 2026-05-12  
**Scope**: 4 notebooks, 5+ warehouse tables

---

## Entities & Merge Keys

### 1. Behavioral Cluster (Notebook: 02_behavioral_clustering)

**Table**: `data/warehouse/beh_clusters`

**Entity**: Groups of user interests and platform engagement patterns

**Attributes**:
- `cluster_id` (unique identifier) — Integer or string uniquely identifying this cluster
- `platform_diversity` — How many distinct platforms are represented
- `engagement_score` — Aggregate engagement metric
- `avg_hour` — Average hour of engagement
- `time_period` — Primary time window (morning, evening, etc.)
- `day_type` — Weekday vs. weekend preference
- `item_count` — Number of items in this cluster
- Other metadata fields

**Merge Key**: `cluster_id`
- **Uniqueness**: ✅ Cluster IDs are unique by design
- **Stability**: ✅ Recomputed deterministically on re-runs
- **Nullability**: ❌ Must never be null

**MERGE Semantics**:
```
WHEN MATCHED THEN UPDATE SET * — Existing clusters get updated metadata
WHEN NOT MATCHED THEN INSERT * — New clusters are added
```

**Initial Create**: `.mode("overwrite")` creates table; subsequent runs use MERGE

---

### 2. Interest Profile (Notebook: 03_fusion_visualization)

**Table**: `data/warehouse/interest_profiles`

**Entity**: Summary profiles for each behavioral cluster with keywords and samples

**Attributes**:
- `cluster_id` (unique identifier) — Foreign key to beh_clusters
- `label` — Human-readable cluster label (e.g., "Nature Explorer")
- `emoji` — Emoji representing cluster personality
- `keywords` — Array of top keywords from cluster sources
- `top_platforms` — Array of dominant platforms (Instagram, Spotify, YouTube, etc.)
- `avg_hour` — Average hour of activity
- `time_period` — Time window (morning, evening, night)
- `day_type` — Weekday vs. weekend
- `item_count` — Total items in cluster
- `sample_items` — Array of sample content snippets

**Merge Key**: `cluster_id`
- **Uniqueness**: ✅ One profile per cluster
- **Stability**: ✅ Based on cluster_id (stable)
- **Nullability**: ❌ Must never be null

**MERGE Semantics**:
```
WHEN MATCHED THEN UPDATE SET * — Profiles updated when cluster keywords/samples change
WHEN NOT MATCHED THEN INSERT * — New profiles created when new clusters found
```

**Parent relationship**: Dependent on `beh_clusters` via cluster_id

---

### 3. Visual Embedding (Notebook: 01_visual_embeddings)

**Table**: `data/warehouse/visual_embeddings`

**Entity**: ML embedding vectors for image content (e.g., CLIP embeddings)

**Attributes**:
- `image_id` (unique identifier) — Stable identifier for image source
- `image_hash` — Content hash (alternative/supplementary key)
- `embedding` — Vector embedding (float array, e.g., 512-dim or 1024-dim)
- `model_version` — Version of embedding model used (e.g., "CLIP-v1")
- `created_date` — When embedding was generated
- `updated_date` — Last time embedding was recomputed
- Other metadata (image source, dimensions, etc.)

**Merge Key**: `image_id` (or composite: `image_hash`)
- **Uniqueness**: ✅ Image IDs are unique
- **Stability**: ✅ Image IDs remain constant
- **Nullability**: ❌ Must never be null

**MERGE Semantics**:
```
WHEN MATCHED THEN UPDATE SET * — Embeddings updated if model version improves
WHEN NOT MATCHED THEN INSERT * — New images get new embeddings
```

**Handling updates**:
- Same image with old embedding: MERGE updates to new embedding + new model_version
- New image: INSERT creates new embedding record
- Deleted image: Image record remains (soft-delete via status flag if needed)

---

### 4. Scene Cluster (Notebook: 02_scene_clustering)

**Table**: `data/warehouse/scene_clusters`

**Entity**: Groupings of images by detected scene characteristics (e.g., indoor/outdoor, time of day)

**Attributes**:
- `scene_id` (unique identifier) — Cluster ID for this scene grouping
- `scene_type` — Type of scene (e.g., "indoor", "outdoor", "night")
- `dominant_hours` — Most common hours for this scene
- `dominant_day` — Weekday vs. weekend preference
- `sample_count` — Number of images in scene
- `avg_image_count_per_day` — Average frequency

**Merge Key**: `scene_id`
- **Uniqueness**: ✅ Scene IDs are unique
- **Stability**: ✅ Recomputed deterministically
- **Nullability**: ❌ Must never be null

**MERGE Semantics**:
```
WHEN MATCHED THEN UPDATE SET * — Scenes updated if characteristics refined
WHEN NOT MATCHED THEN INSERT * — New scene types discovered
```

---

### 5. Scene Samples (Notebook: 02_scene_clustering)

**Table**: `data/warehouse/scene_samples`

**Entity**: Sample images within each scene cluster

**Attributes**:
- `scene_id` (foreign key) — Links to scene_clusters
- `sample_index` (position indicator) — Which sample (1st, 2nd, etc. in this scene)
- `image_id` (foreign key) — Link to visual_embeddings
- `display_order` — Ranking within scene (if applicable)

**Merge Key**: Composite (`scene_id`, `sample_index`) or (`scene_id`, `image_id`)
- **Uniqueness**: ✅ Composite key unique
- **Stability**: ✅ Determined by cluster algorithm
- **Nullability**: ❌ Keys must never be null

**MERGE Semantics**:
```
WHEN MATCHED THEN UPDATE SET display_order = source.display_order
WHEN NOT MATCHED THEN INSERT *
```

**Parent relationships**: 
- Foreign key to `scene_clusters` (scene_id)
- Foreign key to `visual_embeddings` (image_id)

---

## Data Flow & Relationships

```
beh_clusters (behavioral grouping)
        ↓
        └─→ interest_profiles (summary with keywords)

visual_embeddings (image ML vectors)
        ↓
        └─→ scene_clusters (image grouping by scene)
                ↓
                └─→ scene_samples (sample images per scene)
```

---

## Merge Key Strategy Summary

| Entity | Table | Merge Key | Type | First Run |
|--------|-------|-----------|------|-----------|
| Behavioral Cluster | `beh_clusters` | `cluster_id` | Integer | `.mode("overwrite")` |
| Interest Profile | `interest_profiles` | `cluster_id` | Integer | `.mode("overwrite")` |
| Visual Embedding | `visual_embeddings` | `image_id` | String/Hash | `.mode("overwrite")` |
| Scene Cluster | `scene_clusters` | `scene_id` | Integer | `.mode("overwrite")` |
| Scene Sample | `scene_samples` | (`scene_id`, `sample_index`) or (`scene_id`, `image_id`) | Composite | `.mode("overwrite")` |

---

## Validation & Constraints

### Per-Entity Constraints

**Behavioral Cluster**:
- `cluster_id` is never null ✓
- `cluster_id` is unique ✓
- Cannot delete (only update via MERGE)

**Interest Profile**:
- `cluster_id` is never null ✓
- `cluster_id` is unique ✓
- Foreign key: `cluster_id` must exist in `beh_clusters`

**Visual Embedding**:
- `image_id` is never null ✓
- `image_id` is unique ✓
- `model_version` documents how embedding was created

**Scene Cluster**:
- `scene_id` is never null ✓
- `scene_id` is unique ✓
- Cannot delete (only update via MERGE)

**Scene Sample**:
- Composite key (`scene_id`, `sample_index`) is never null ✓
- Composite key is unique ✓
- Foreign keys: `scene_id` must exist in `scene_clusters`, `image_id` must exist in `visual_embeddings`

---

## Schema Evolution

**Handling new columns** (Delta auto-detects):
- If source DF adds a column, Delta adds it to target table
- Existing rows get null for new column (unless transformed)

**Recommended approach**:
- Document expected schema in notebook markdown cell
- Use `WHEN MATCHED THEN UPDATE SET *` (simple, handles new columns)
- For fine-grained control: Use explicit column list in UPDATE clause

**Example**:
```python
# Explicit schema control (optional)
spark.sql(f"""
  MERGE INTO target
  USING source
  ON target.cluster_id = source.cluster_id
  WHEN MATCHED THEN UPDATE SET 
    target.label = source.label,
    target.keywords = source.keywords,
    target.updated_date = current_timestamp()
  WHEN NOT MATCHED THEN INSERT (cluster_id, label, keywords, created_date, updated_date) 
    VALUES (source.cluster_id, source.label, source.keywords, current_timestamp(), current_timestamp())
""")
```

---

## Performance Notes

**No indexing required** for this fix (Delta handles)

**Future optimization** (not in scope):
- Partition keys (e.g., by date range) for large tables
- Z-order clustering for merge-key columns
- Data skipping statistics

---

**Conclusion**: All 5 entities are well-defined with stable, unique merge keys. MERGE INTO patterns will ensure idempotency and data consistency.
