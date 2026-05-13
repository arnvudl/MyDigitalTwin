import sys
import os

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

from config import build_spark_session, WAREHOUSE  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    StructType,
    StructField,
    StringType,
    IntegerType,
    LongType,
    ArrayType,
    FloatType,
)
from delta.tables import DeltaTable  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
import re  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402


def _load_config() -> dict:
    config_path = os.path.join(_d, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("memory_album", {})
    return {}


def _date_from_filename(filename: str):
    """Extract date from common photo filename patterns."""
    patterns = [
        r"(\d{4})[-_](\d{2})[-_](\d{2})",
        r"(\d{4})(\d{2})(\d{2})",
        r"IMG[-_](\d{4})(\d{2})(\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, filename)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except Exception:
                continue
    return None


def time_slot(dt: datetime, gap_hours: float) -> str:
    """Round datetime down to the nearest gap_hours bucket."""
    epoch = datetime(2000, 1, 1)
    slots = int((dt - epoch).total_seconds() / (gap_hours * 3600))
    slot_start = epoch + timedelta(hours=slots * gap_hours)
    return slot_start.strftime("%Y-%m-%d_%H")


def group_label(scene_id: int, dt) -> str:
    if dt is not None:
        return dt.strftime(f"Scene {scene_id:04d} — %Y-%m-%d")
    return f"Scene {scene_id:04d}"


def main():
    spark = build_spark_session(
        "MyDigitalTwin-MemoryAlbum-Clustering",
        driver_memory="4g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        ma_config = _load_config()
        gap_hours = float(ma_config.get("scene_gap_hours", 6.0))

        emb_path = os.path.join(WAREHOUSE, "memory_album", "photo_embeddings")
        if not os.path.isdir(emb_path):
            print("  ⚠ photo_embeddings introuvable — run 01_visual_embeddings.py first")
            return

        df = spark.read.format("delta").load(emb_path)

        # Collect to pandas for temporal/cosine grouping
        pdf = df.select("photo_id", "photo_path", "photo_date", "embedding").toPandas()

        # Parse dates
        pdf["_dt"] = pdf["photo_date"].apply(
            lambda d: datetime.fromisoformat(d) if d else None
        )
        pdf["_dt_from_fn"] = pdf["photo_path"].apply(
            lambda p: _date_from_filename(os.path.basename(p))
        )
        pdf["_resolved_dt"] = pdf.apply(
            lambda r: r["_dt"] if r["_dt"] is not None else r["_dt_from_fn"], axis=1
        )

        # Temporal clustering: photos with dates → group by time slot
        dated = pdf[pdf["_resolved_dt"].notna()].copy()
        undated = pdf[pdf["_resolved_dt"].isna()].copy()

        scene_id = 0
        scene_rows = []
        centroid_rows = []

        if not dated.empty:
            dated["_slot"] = dated["_resolved_dt"].apply(lambda dt: time_slot(dt, gap_hours))
            for slot, group in dated.groupby("_slot"):
                scene_id += 1
                rep_dt = group["_resolved_dt"].iloc[0]
                for _, row in group.iterrows():
                    scene_rows.append({
                        "photo_id": row["photo_id"],
                        "scene_id": scene_id,
                        "scene_label": group_label(scene_id, rep_dt),
                        "assignment_method": "temporal",
                    })
                # Centroid: mean of embeddings
                embs = [e for e in group["embedding"].tolist() if e]
                if embs:
                    centroid = np.mean(embs, axis=0).tolist()
                else:
                    centroid = []
                centroid_rows.append({
                    "scene_id": scene_id,
                    "scene_label": group_label(scene_id, rep_dt),
                    "centroid": centroid,
                    "photo_count": len(group),
                })

        # Undated photos: cosine similarity to nearest centroid, or new scene
        if not undated.empty and centroid_rows:
            centroids_arr = np.array([c["centroid"] for c in centroid_rows if c["centroid"]])
            for _, row in undated.iterrows():
                emb = row["embedding"]
                if emb and centroids_arr.shape[0] > 0:
                    emb_arr = np.array(emb)
                    norms = np.linalg.norm(centroids_arr, axis=1) * np.linalg.norm(emb_arr)
                    sims = np.dot(centroids_arr, emb_arr) / (norms + 1e-8)
                    best_idx = int(np.argmax(sims))
                    best_scene = centroid_rows[best_idx]["scene_id"]
                    best_label = centroid_rows[best_idx]["scene_label"]
                else:
                    scene_id += 1
                    best_scene = scene_id
                    best_label = f"Scene {scene_id:04d}"
                scene_rows.append({
                    "photo_id": row["photo_id"],
                    "scene_id": best_scene,
                    "scene_label": best_label,
                    "assignment_method": "cosine",
                })
        elif not undated.empty:
            for _, row in undated.iterrows():
                scene_id += 1
                scene_rows.append({
                    "photo_id": row["photo_id"],
                    "scene_id": scene_id,
                    "scene_label": f"Scene {scene_id:04d}",
                    "assignment_method": "fallback",
                })

        scenes_schema = StructType([
            StructField("photo_id", StringType()),
            StructField("scene_id", IntegerType()),
            StructField("scene_label", StringType()),
            StructField("assignment_method", StringType()),
        ])
        df_scenes = spark.createDataFrame(scene_rows, schema=scenes_schema)

        centroids_schema = StructType([
            StructField("scene_id", IntegerType()),
            StructField("scene_label", StringType()),
            StructField("centroid", ArrayType(FloatType())),
            StructField("photo_count", IntegerType()),
        ])
        df_centroids = spark.createDataFrame(centroid_rows, schema=centroids_schema)

        # Computed tables → delete + append
        scenes_path = os.path.join(WAREHOUSE, "memory_album", "scenes")
        if DeltaTable.isDeltaTable(spark, scenes_path):
            DeltaTable.forPath(spark, scenes_path).delete()
            df_scenes.write.format("delta").mode("append").save(scenes_path)
        else:
            df_scenes.write.format("delta").mode("overwrite").save(scenes_path)
        print(f"  ✓ memory_album/scenes — {df_scenes.count():,} lignes")

        centroids_path = os.path.join(WAREHOUSE, "memory_album", "scene_centroids")
        if DeltaTable.isDeltaTable(spark, centroids_path):
            DeltaTable.forPath(spark, centroids_path).delete()
            df_centroids.write.format("delta").mode("append").save(centroids_path)
        else:
            df_centroids.write.format("delta").mode("overwrite").save(centroids_path)
        print(f"  ✓ memory_album/scene_centroids — {df_centroids.count():,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
