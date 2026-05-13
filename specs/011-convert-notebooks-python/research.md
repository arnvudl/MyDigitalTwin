# Research: Convert Notebooks to Production Python Scripts

**Feature**: 011-convert-notebooks-python  
**Date**: 2026-05-13

---

## Decision 1: Spark Session Strategy

**Decision**: Use `build_spark_session()` from `config.py` — already exists and is Docker-aware.

**Rationale**: 
- `build_spark_session()` accepts `app_name`, `driver_memory`, `shuffle_partitions` as parameters
- Default is `driver_memory="4g"` — appropriate for most scripts
- Heavy scripts (02_clusters, 05_CLIP with embeddings) should use `driver_memory="2g"` + `shuffle_partitions=4` to stay within Docker limits
- Light scripts (01_exploration) can use the default `driver_memory="2g"`, `shuffle_partitions=4`
- Call `spark.stop()` at end of every script via `try/finally` block

**Alternatives considered**:
- Shared session across scripts via singleton: rejected — makes individual execution impossible and risks memory leaks
- SparkContext with manual config: rejected — `build_spark_session()` already handles this cleanly

---

## Decision 2: Handling Exploration Cells

**Decision**: Remove all exploration/display cells entirely (`.show()`, `.printSchema()`, `.groupBy().count().show()`, `print(...)` stats).

**Rationale**:
- Production scripts should produce zero console noise beyond status logs
- These cells trigger Spark jobs that compute and discard results — pure RAM waste in Docker
- The dashboard is the correct place to display analytics
- Only keep `print(f"✓ table_name -- {n} rows written")` at write checkpoints for traceability

**Alternatives considered**:
- Redirect to logger: overkill for this project, adds complexity
- Keep as commented code: rejected — noise in production files

---

## Decision 3: Handling the Hardcoded PARQUET_DIR in instagram.ipynb

**Decision**: Remove `PARQUET_DIR` entirely — it was a leftover development path and is never used in write operations (all writes already use `WAREHOUSE`).

**Rationale**: Only `WAREHOUSE` and `PROCESSED_DATA` from `config.py` are used in actual Delta writes. The `PARQUET_DIR` variable was defined but unused in production writes.

---

## Decision 4: run_pipeline.py Architecture

**Decision**: `run_pipeline.py` at project root uses `subprocess.run()` to call each script individually, preserving independent session lifecycle per script.

**Rationale**:
- Each script must call `spark.stop()` — impossible if they share a process via imports
- `subprocess.run()` gives clean process isolation = no memory leakage between stages
- Supports `--stage` argument to run a single stage by name or index
- Supports `--from` and `--to` to run a range of stages

**Alternatives considered**:
- Direct function calls via imports: rejected — Spark sessions can't be cleanly stopped/restarted in the same process
- Makefile: rejected — adds non-Python dependency

---

## Decision 5: validate_outputs.py Strategy

**Decision**: Read Delta table metadata (schema + row count) and compare against a hardcoded expectations dict. Runs as a standalone script post-conversion.

**Rationale**:
- Simple, zero-dependency approach (only PySpark needed)
- Expectations = dict of `{table_name: {"min_rows": N, "required_columns": [...]}}` 
- Delta format supports efficient metadata reads without full table scan for schema check
- Row count uses `spark.read.format("delta").load(path).count()` — acceptable for smoke test
- Exits with code 0 (pass) or 1 (fail) for CI integration

---

## Decision 6: Memory Config per Script (valeurs réelles extraites des notebooks)

Les valeurs ci-dessous sont copiées fidèlement depuis les appels `build_spark_session()` existants dans chaque notebook. Aucune valeur n'est inventée.

| Script | app_name | driver_memory | shuffle_partitions | snappy | delta | Notes |
|---|---|---|---|---|---|---|
| `01_exploration/instagram.py` | `MyDigitalTwin - Instagram` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `01_exploration/google_youtube.py` | `MyDigitalTwin - Google` | **`6g`** | `8` (défaut) | False | False | Dataset YouTube volumineux |
| `01_exploration/spotify.py` | `MyDigitalTwin - Spotify` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `01_exploration/tiktok.py` | `MyDigitalTwin - TikTok` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `01_exploration/twitter.py` | `MyDigitalTwin - Twitter` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `01_exploration/netflix.py` | `MyDigitalTwin - Netflix` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `02_clusters/01_content_clustering.py` | `MyDigitalTwin-FrequencyAnalysis` | `4g` (défaut) | `8` (défaut) | False | True | — |
| `02_clusters/02_behavioral_clustering.py` | `MyDigitalTwin-BehavioralClustering` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `02_clusters/03_fusion_visualization.py` | `MyDigitalTwin-FusionViz` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `03_memory_album/01_visual_embeddings.py` | `MyDigitalTwin-MemoryAlbum-Embeddings` | **`4g`** (explicite) | `8` (défaut) | **True** | **True** | Snappy requis pour embeddings |
| `03_memory_album/02_scene_clustering.py` | `MyDigitalTwin-MemoryAlbum-Clustering` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `03_memory_album/03_music_matching.py` | `MyDigitalTwin-MemoryAlbum-MusicMatching` | `4g` (défaut) | `8` (défaut) | False | False | — |
| `05_CLIP/01_clip_embeddings.py` | `MyDigitalTwin-CLIP-Embeddings` | `4g` (défaut) | `8` (défaut) | **True** | **True** | Snappy + Delta requis |
| `05_CLIP/02_clip_clustering.py` | `MyDigitalTwin-CLIP-Clustering-V2` | `4g` (défaut) | `8` (défaut) | False | **True** | Utilise `.cache()` — légitime ici |
| `06_social/01_social_graph.py` | **N/A — PAS DE SPARK** | — | — | — | — | Pure Python/JSON séquentiel, ~100 nœuds max |

**Règle** : reproduire exactement les paramètres du notebook. Ne rien changer sans raison explicite.
