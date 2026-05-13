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
    ArrayType,
    FloatType,
)
from delta.tables import DeltaTable  # noqa: E402
import numpy as np  # noqa: E402


# Hardcoded cluster labels from notebook source
cluster_labels = {
    0: "Nature & Outdoors",
    1: "Urban & Architecture",
    2: "People & Portraits",
    3: "Food & Dining",
    4: "Travel & Landmarks",
    5: "Sports & Activities",
    6: "Events & Celebrations",
    7: "Animals & Pets",
    -1: "Uncategorized",
}


def main():
    spark = build_spark_session(
        "MyDigitalTwin-CLIP-Clustering-V2",
        driver_memory="4g",
        shuffle_partitions=8,
        delta=True,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        emb_path = os.path.join(WAREHOUSE, "photo_embeddings")
        if not os.path.isdir(emb_path):
            print("  ⚠ photo_embeddings introuvable — run 01_clip_embeddings.py first")
            return

        df = spark.read.format("delta").load(emb_path)

        # .cache() is legitimate here: embeddings reused multiple times in UMAP+HDBSCAN
        df = df.cache()

        # Collect embeddings — small dataset (~2420 photos)
        rows = df.select("filename", "embedding").collect()
        filenames = [r["filename"] for r in rows]
        embs = np.array([r["embedding"] for r in rows], dtype=np.float32)

        if len(embs) == 0:
            print("  ⚠ No embeddings found")
            return

        # UMAP: 768D → 50D for HDBSCAN, 2D for visualization reference
        import umap
        reducer_50 = umap.UMAP(n_components=50, metric="cosine", random_state=42)
        embs_50 = reducer_50.fit_transform(embs)

        # HDBSCAN clustering
        import hdbscan
        clusterer = hdbscan.HDBSCAN(min_cluster_size=50, min_samples=5, metric="euclidean")
        cluster_ids = clusterer.fit_predict(embs_50).tolist()

        # 2D UMAP for coordinate reference (stored for dashboard)
        reducer_2 = umap.UMAP(n_components=2, metric="cosine", random_state=42)
        embs_2 = reducer_2.fit_transform(embs)

        result_rows = []
        for fname, cid, coord in zip(filenames, cluster_ids, embs_2):
            label = cluster_labels.get(int(cid), f"Cluster {cid}")
            result_rows.append({
                "filename": fname,
                "cluster_id": int(cid),
                "cluster_label": label,
                "umap_x": float(coord[0]),
                "umap_y": float(coord[1]),
            })

        schema = StructType([
            StructField("filename", StringType()),
            StructField("cluster_id", IntegerType()),
            StructField("cluster_label", StringType()),
            StructField("umap_x", FloatType()),
            StructField("umap_y", FloatType()),
        ])
        df_clusters = spark.createDataFrame(result_rows, schema=schema)

        # Computed table → delete + append
        table_path = os.path.join(WAREHOUSE, "photo_clusters")
        if DeltaTable.isDeltaTable(spark, table_path):
            DeltaTable.forPath(spark, table_path).delete()
            df_clusters.write.format("delta").mode("append").save(table_path)
        else:
            df_clusters.write.format("delta").mode("overwrite").save(table_path)

        count = spark.read.format("delta").load(table_path).count()
        print(f"  ✓ photo_clusters — {count:,} lignes")

        df.unpersist()

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
