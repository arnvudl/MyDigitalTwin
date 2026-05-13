import sys
import os

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
    MUSIC_LIBRARY_PATH,
)
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    StructType,
    StructField,
    StringType,
    IntegerType,
    FloatType,
)
import json  # noqa: E402
import yaml  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402


def _load_config() -> dict:
    config_path = os.path.join(_d, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("memory_album", {})
    return {}


def _load_music_library() -> list[dict]:
    if not os.path.exists(MUSIC_LIBRARY_PATH):
        return []
    with open(MUSIC_LIBRARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def temporal_match(photo_dt: datetime, music_lib: list, window_minutes: float) -> dict | None:
    """Find track played within window_minutes of photo timestamp."""
    if photo_dt is None:
        return None
    window = timedelta(minutes=window_minutes)
    best = None
    best_delta = window
    for track in music_lib:
        try:
            track_dt = datetime.fromisoformat(track.get("ts", ""))
        except Exception:
            continue
        delta = abs(photo_dt - track_dt)
        if delta <= best_delta:
            best_delta = delta
            best = track
    return best


def semantic_match(caption: str, music_lib: list, model) -> dict | None:
    """Find track with highest semantic similarity to photo caption."""
    if not caption or not music_lib:
        return None
    try:
        track_texts = [f"{t.get('track_name', '')} {t.get('artist_name', '')}" for t in music_lib]
        embs = model.encode([caption] + track_texts, convert_to_numpy=True)
        caption_emb = embs[0]
        track_embs = embs[1:]
        import numpy as np
        sims = np.dot(track_embs, caption_emb) / (
            np.linalg.norm(track_embs, axis=1) * np.linalg.norm(caption_emb) + 1e-8
        )
        best_idx = int(sims.argmax())
        return music_lib[best_idx] if float(sims[best_idx]) > 0.3 else None
    except Exception:
        return None


def best_match(photo_id: str, photo_dt, caption: str, music_lib: list, model,
               temporal_window: float, manual_overrides: dict) -> dict:
    """Priority: manual → temporal → semantic caption → fallback."""
    if photo_id in manual_overrides:
        override = manual_overrides[photo_id]
        return {"method": "manual", "track_name": override.get("track"), "artist_name": override.get("artist")}

    match = temporal_match(photo_dt, music_lib, temporal_window)
    if match:
        return {"method": "temporal", "track_name": match.get("track_name"), "artist_name": match.get("artist_name")}

    match = semantic_match(caption, music_lib, model)
    if match:
        return {"method": "semantic_caption", "track_name": match.get("track_name"), "artist_name": match.get("artist_name")}

    # Temporal 3h fallback
    match = temporal_match(photo_dt, music_lib, temporal_window * 3)
    if match:
        return {"method": "temporal_3h", "track_name": match.get("track_name"), "artist_name": match.get("artist_name")}

    return {"method": "fallback", "track_name": None, "artist_name": None}


def main():
    spark = build_spark_session(
        "MyDigitalTwin-MemoryAlbum-MusicMatching",
        driver_memory="4g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        ma_config = _load_config()
        temporal_window = float(ma_config.get("temporal_window_minutes", 30.0))
        manual_overrides = ma_config.get("manual_overrides", {})

        music_lib = _load_music_library()
        if not music_lib:
            print(f"  ⚠ Music library not found at {MUSIC_LIBRARY_PATH}")

        emb_path = os.path.join(WAREHOUSE, "memory_album", "photo_embeddings")
        if not os.path.isdir(emb_path):
            print("  ⚠ photo_embeddings introuvable — run 01_visual_embeddings.py first")
            return

        df = spark.read.format("delta").load(emb_path).select(
            "photo_id", "photo_date", "caption", "scene_id" if "scene_id" in spark.read.format("delta").load(emb_path).columns else F.lit(None).alias("scene_id")
        )
        pdf = df.toPandas()

        # Load semantic model once
        try:
            from sentence_transformers import SentenceTransformer
            sem_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            sem_model = None

        match_rows = []
        for _, row in pdf.iterrows():
            photo_dt = None
            if row.get("photo_date"):
                try:
                    photo_dt = datetime.fromisoformat(str(row["photo_date"]))
                except Exception:
                    pass
            match = best_match(
                str(row["photo_id"]),
                photo_dt,
                str(row.get("caption") or ""),
                music_lib,
                sem_model,
                temporal_window,
                manual_overrides,
            )
            match_rows.append({
                "photo_id": str(row["photo_id"]),
                "track_name": match.get("track_name"),
                "artist_name": match.get("artist_name"),
                "method": match.get("method"),
                "scene_id": row.get("scene_id"),
            })

        schema = StructType([
            StructField("photo_id", StringType()),
            StructField("track_name", StringType()),
            StructField("artist_name", StringType()),
            StructField("method", StringType()),
            StructField("scene_id", IntegerType()),
        ])
        df_matches = spark.createDataFrame(match_rows, schema=schema)
        df_matches.write.format("delta").mode("overwrite").save(os.path.join(WAREHOUSE, "music_matches"))
        print(f"  ✓ music_matches — {df_matches.count():,} lignes")

        # photo_music: join embeddings with matches
        df_photo_music = df.join(df_matches, on="photo_id", how="left")
        df_photo_music.write.format("delta").mode("overwrite").save(os.path.join(WAREHOUSE, "photo_music"))
        print(f"  ✓ photo_music — {df_photo_music.count():,} lignes")

        # group_playlists: aggregate by scene
        df_playlists = (
            df_matches
            .filter(F.col("scene_id").isNotNull() & F.col("track_name").isNotNull())
            .groupBy("scene_id", "track_name", "artist_name")
            .agg(F.count("*").alias("photo_count"))
            .orderBy("scene_id", F.desc("photo_count"))
        )
        df_playlists.write.format("delta").mode("overwrite").save(os.path.join(WAREHOUSE, "group_playlists"))
        print(f"  ✓ group_playlists — {df_playlists.count():,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
