import sys
import os
from pathlib import Path

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

import numpy as np  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    StructType, StructField, StringType, IntegerType, FloatType,
)
from delta.tables import DeltaTable  # noqa: E402
from config import build_spark_session, WAREHOUSE, CLIP_CANDIDATE_LABELS  # noqa: E402


EMBEDDINGS_DIR = Path(WAREHOUSE) / "photo_embeddings"
CLUSTERS_DIR   = Path(WAREHOUSE) / "photo_clusters"

cluster_labels = {
    -1: "Souvenir en tout genre",
     0: "photos d'enfance",
     1: "Memes et Humour",
     2: "MDR ya que des meufs",
     3: "Voyage Rhéto",
     4: "Fourre-Tout",
     5: "Soirées"
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
        embeddings_path = str(EMBEDDINGS_DIR)
        if DeltaTable.isDeltaTable(spark, embeddings_path):
            df = spark.read.format("delta").load(embeddings_path).cache()
        else:
            df = spark.read.parquet(embeddings_path).cache()

        print(f"Photos chargées : {df.count()}")

        rows = df.select("photo_path", "filename", "embedding").collect()
        paths     = [r["photo_path"] for r in rows]
        filenames = [r["filename"]   for r in rows]
        X = np.array([r["embedding"] for r in rows], dtype=np.float32)

        print(f"Shape embeddings : {X.shape}")

        # ── UMAP 768D → 50D (clustering) + 2D (visualization) ────────────────
        import umap

        print("1/2 - UMAP 768D -> 50D (clustering)...")
        reducer_50 = umap.UMAP(
            n_components=50,
            n_neighbors=15,
            min_dist=0.1,
            metric="cosine",
            random_state=42,
            verbose=True,
        )
        X_50 = reducer_50.fit_transform(X)
        print(f"Shape après UMAP 50D : {X_50.shape}")

        print("2/2 - UMAP 768D -> 2D (visualisation dashboard)...")
        reducer_2d = umap.UMAP(
            n_components=2,
            n_neighbors=15,
            min_dist=0.1,
            metric="cosine",
            random_state=42,
        )
        X_2d = reducer_2d.fit_transform(X)
        print(f"Shape UMAP 2D : {X_2d.shape}")

        # ── HDBSCAN ───────────────────────────────────────────────────────────
        import hdbscan

        print("HDBSCAN...")
        clustering = hdbscan.HDBSCAN(
            min_cluster_size=60,
            min_samples=5,
            metric="euclidean",
            cluster_selection_method="eom",
        )
        labels = clustering.fit_predict(X_50)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise    = (labels == -1).sum()
        print(f"Clusters trouvés : {n_clusters}")
        print(f"Outliers (bruit) : {n_noise} photos ({n_noise/len(labels)*100:.1f}%)")

        # ── Write Delta ───────────────────────────────────────────────────────
        rows_out = [
            (
                paths[i],
                filenames[i],
                int(labels[i]),
                cluster_labels.get(int(labels[i]), f"Cluster {labels[i]}"),
                float(X_2d[i, 0]),
                float(X_2d[i, 1]),
            )
            for i in range(len(paths))
        ]

        schema = StructType([
            StructField("path",          StringType(),  nullable=False),
            StructField("filename",      StringType(),  nullable=False),
            StructField("cluster",       IntegerType(), nullable=False),
            StructField("cluster_label", StringType(),  nullable=False),
            StructField("umap_x",        FloatType(),   nullable=False),
            StructField("umap_y",        FloatType(),   nullable=False),
        ])

        df_out = spark.createDataFrame(rows_out, schema=schema)

        clusters_path = str(CLUSTERS_DIR)
        CLUSTERS_DIR.mkdir(parents=True, exist_ok=True)
        if DeltaTable.isDeltaTable(spark, clusters_path):
            DeltaTable.forPath(spark, clusters_path).delete()
            df_out.write.format("delta").mode("append").save(clusters_path)
        else:
            df_out.write.format("delta").mode("overwrite").save(clusters_path)

        count = spark.read.format("delta").load(clusters_path).count()
        print(f"  ✓ photo_clusters — {count:,} lignes")

        df.unpersist()

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
