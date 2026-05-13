import os
import sys

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

from config import (  # noqa: E402
    build_spark_session,
    WAREHOUSE,
    PHOTO_SORTING_DIR,
)
from pyspark.sql.types import (  # noqa: E402
    StructType,
    StructField,
    StringType,
    FloatType,
    IntegerType,
    ArrayType,
)
from delta.tables import DeltaTable  # noqa: E402
import glob  # noqa: E402
import numpy as np  # noqa: E402


CLIP_MODEL = "openai/clip-vit-large-patch14"
BATCH_SIZE = 32


def run_inference(photo_files: list) -> list:
    """Pure Python inference loop — faithful to the notebook approach."""
    import torch
    from transformers import CLIPVisionModelWithProjection, CLIPImageProcessor
    from PIL import Image

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = CLIPImageProcessor.from_pretrained(CLIP_MODEL)
    model = CLIPVisionModelWithProjection.from_pretrained(CLIP_MODEL).to(device)
    model.eval()
    print(f"  CLIP model loaded on {device}")

    rows = []
    total = len(photo_files)
    for i in range(0, total, BATCH_SIZE):
        batch_paths = photo_files[i:i + BATCH_SIZE]
        print(f"  [{min(i + BATCH_SIZE, total)}/{total}] batch {i // BATCH_SIZE + 1}", flush=True)
        imgs = []
        valid_paths = []
        for path in batch_paths:
            try:
                imgs.append(Image.open(path).convert("RGB"))
                valid_paths.append(path)
            except Exception as e:
                print(f"  ⚠ {os.path.basename(path)}: {e}")

        if not imgs:
            continue

        inputs = processor(images=imgs, return_tensors="pt").to(device)
        with torch.no_grad():
            embs = model(**inputs).image_embeds.cpu().numpy()

        # L2 normalize
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        embs = embs / (norms + 1e-8)

        for path, emb in zip(valid_paths, embs):
            rows.append({
                "filename": os.path.basename(path),
                "photo_path": path,
                "embedding": emb.tolist(),
                "embedding_dim": len(emb),
            })

    return rows


def main():
    spark = build_spark_session(
        "MyDigitalTwin-CLIP-Embeddings",
        driver_memory="4g",
        shuffle_partitions=8,
        delta=True,
        snappy=True,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        photo_files = []
        for ext in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG"):
            photo_files += glob.glob(os.path.join(PHOTO_SORTING_DIR, "**", ext), recursive=True)

        if not photo_files:
            print(f"  ⚠ No photos found in {PHOTO_SORTING_DIR}")
            return

        print(f"  {len(photo_files)} photos found — running CLIP inference...")
        rows = run_inference(photo_files)

        if not rows:
            print("  ⚠ No embeddings generated")
            return

        schema = StructType([
            StructField("filename", StringType()),
            StructField("photo_path", StringType()),
            StructField("embedding", ArrayType(FloatType())),
            StructField("embedding_dim", IntegerType()),
        ])

        df = spark.createDataFrame(rows, schema=schema)

        table_path = os.path.join(WAREHOUSE, "photo_embeddings")
        if DeltaTable.isDeltaTable(spark, table_path):
            DeltaTable.forPath(spark, table_path).alias("t").merge(
                df.alias("s"), "t.filename = s.filename"
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
        else:
            df.write.format("delta").mode("overwrite").save(table_path)

        count = spark.read.format("delta").load(table_path).count()
        print(f"  ✓ photo_embeddings — {count:,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
