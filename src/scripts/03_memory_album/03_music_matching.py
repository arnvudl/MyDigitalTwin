import sys
import os

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

import json  # noqa: E402
import yaml  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from config import (  # noqa: E402
    build_spark_session,
    MEMORY_ALBUM_DIR,
    WAREHOUSE,
    MUSIC_LIBRARY_PATH,
    MODELS_CACHE_DIR,
)


CENTROIDS_DIR   = os.path.join(MEMORY_ALBUM_DIR, "scene_centroids")
SCENES_DIR      = os.path.join(MEMORY_ALBUM_DIR, "scenes")
STREAMS_DIR     = os.path.join(WAREHOUSE, "spotify_streams")
MATCHES_DIR     = os.path.join(MEMORY_ALBUM_DIR, "music_matches")
PHOTO_MUSIC_DIR = os.path.join(MEMORY_ALBUM_DIR, "photo_music")
PLAYLISTS_DIR   = os.path.join(MEMORY_ALBUM_DIR, "group_playlists")


def _normalize_tid(tid: str) -> str:
    if not tid:
        return tid
    return tid if tid.startswith("spotify:track:") else f"spotify:track:{tid}"


def _time_context(ts) -> str:
    if ts is None or pd.isna(ts):
        return ""
    dt = pd.Timestamp(ts)
    h  = dt.hour
    m  = dt.month
    season = "winter" if m in (12, 1, 2) else "spring" if m in (3, 4, 5) \
             else "summer" if m in (6, 7, 8) else "autumn"
    if   0 <= h < 6:   slot = "late night dark quiet"
    elif 6 <= h < 12:  slot = "morning fresh start energy"
    elif 12 <= h < 18: slot = "afternoon chill sunny"
    elif 18 <= h < 23: slot = "evening friends social vibes"
    else:              slot = "night out party"
    return f"{slot} {season}"


def main():
    cfg_path = os.path.join(_d, "config.yaml")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    ma = cfg.get("memory_album", {})
    temporal_window_min = int(ma.get("temporal_window_minutes", 60))
    manual_overrides    = ma.get("manual_overrides", [])
    print(f"Fenêtre temporelle : ±{temporal_window_min} min")
    print(f"Overrides manuels  : {len(manual_overrides)} entrée(s)")

    spark = build_spark_session(
        "MyDigitalTwin-MemoryAlbum-MusicMatching",
        driver_memory="4g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        # ── 3. Load data ──────────────────────────────────────────────────────
        df_centroids = spark.read.format("delta").load(CENTROIDS_DIR)
        print(f"Groupes : {df_centroids.count()}")

        df_scenes_all = spark.read.format("delta").load(SCENES_DIR)
        scenes_pdf = df_scenes_all.select(
            "photo_id", "scene_id", "exif_date", "path", "caption"
        ).toPandas()
        scenes_pdf["exif_date"] = pd.to_datetime(scenes_pdf["exif_date"], errors="coerce")
        print(f"Photos  : {len(scenes_pdf)}")

        has_streams = os.path.exists(STREAMS_DIR)
        if has_streams:
            df_streams = spark.read.format("delta").load(STREAMS_DIR)
            print(f"Streams : {df_streams.count()}")
        else:
            df_streams = None
            print("⚠ Pas de dossier spotify_streams")

        has_library = os.path.exists(MUSIC_LIBRARY_PATH)
        if has_library:
            with open(MUSIC_LIBRARY_PATH, encoding="utf-8") as f:
                music_library = json.load(f)
            print(f"Bibliothèque : {len(music_library)} titres")
        else:
            music_library = []
            print("⚠ music_library.json introuvable")

        # ── 4. Prepare streams ────────────────────────────────────────────────
        streams_pdf = pd.DataFrame()
        if has_streams and df_streams is not None:
            stream_cols  = df_streams.columns
            ts_col       = next((c for c in ["stream_ts", "played_at", "ts", "listen_ts"] if c in stream_cols), None)
            track_id_col = next((c for c in ["track_id", "trackId", "spotify_track_uri", "trackUri"] if c in stream_cols), None)
            track_name_col = next((c for c in ["track_name", "trackName", "master_metadata_track_name"] if c in stream_cols), None)
            artist_col   = next((c for c in ["artist_name", "artistName", "master_metadata_album_artist_name"] if c in stream_cols), None)

            missing = [n for n, c in [("timestamp", ts_col), ("track_id", track_id_col),
                                       ("track_name", track_name_col), ("artist", artist_col)] if c is None]
            if missing:
                print(f"⚠ Colonnes manquantes dans streams : {missing} — matching temporel désactivé")
            else:
                streams_pdf = (
                    df_streams
                    .select(
                        F.col(ts_col).cast("timestamp").alias("stream_ts"),
                        F.col(track_id_col).alias("track_id"),
                        F.col(track_name_col).alias("track_name"),
                        F.col(artist_col).alias("artist_name"),
                    )
                    .filter(F.col("track_id").isNotNull())
                    .toPandas()
                )
                streams_pdf["stream_ts"] = pd.to_datetime(streams_pdf["stream_ts"], errors="coerce")
                streams_pdf = streams_pdf.dropna(subset=["stream_ts"])
                print(f"Streams utilisables : {len(streams_pdf)}")

        # ── 5. Semantic model ─────────────────────────────────────────────────
        library_with_moments = [t for t in music_library if t.get("moments")]
        semantic_ready = False
        moment_embs = None
        model_sem = None

        if library_with_moments:
            try:
                from sentence_transformers import SentenceTransformer
                model_sem = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=MODELS_CACHE_DIR)
                moment_texts = [
                    ", ".join(t["moments"]) if isinstance(t["moments"], list) else str(t["moments"])
                    for t in library_with_moments
                ]
                moment_embs = model_sem.encode(moment_texts, normalize_embeddings=True)
                semantic_ready = True
                print(f"Modèle sémantique chargé — {len(library_with_moments)} titres avec moment tags")
            except Exception as e:
                print(f"⚠ Sémantique indisponible : {e}")

        # ── 6. Matching functions ─────────────────────────────────────────────
        W_SEC = temporal_window_min * 60
        lib_lookup = {t["track_id"]: t for t in music_library}

        photo_overrides = {
            ov["photo_id"]: _normalize_tid(ov["track_id"])
            for ov in manual_overrides
            if ov.get("photo_id") and ov.get("track_id")
        }

        global_fallback = None
        if not streams_pdf.empty:
            top = streams_pdf.groupby(["track_id", "track_name", "artist_name"]).size().idxmax()
            tid, tname, tartist = top
            meta = lib_lookup.get(_normalize_tid(tid), {})
            global_fallback = {
                "track_id": _normalize_tid(tid), "track_name": tname,
                "artist_name": tartist, "album_cover_url": meta.get("album_cover_url", ""),
                "match_type": "fallback", "match_score": 0.0,
            }
        elif music_library:
            t = music_library[0]
            global_fallback = {
                "track_id": t["track_id"], "track_name": t["track_name"],
                "artist_name": t.get("artist", ""), "album_cover_url": t.get("album_cover_url", ""),
                "match_type": "fallback", "match_score": 0.0,
            }

        def temporal_match(ts, window_sec=None):
            if streams_pdf.empty or ts is None or pd.isna(ts):
                return None
            ws = window_sec or W_SEC
            ts = pd.Timestamp(ts)
            mask = (
                (streams_pdf["stream_ts"] >= ts - pd.Timedelta(seconds=ws)) &
                (streams_pdf["stream_ts"] <= ts + pd.Timedelta(seconds=ws))
            )
            hits = streams_pdf[mask]
            if hits.empty:
                return None
            best = hits.groupby(["track_id", "track_name", "artist_name"]).size().idxmax()
            tid, tname, artist = best
            meta = lib_lookup.get(_normalize_tid(tid), {})
            return {
                "track_id": _normalize_tid(tid), "track_name": tname,
                "artist_name": artist, "album_cover_url": meta.get("album_cover_url", ""),
                "match_type": "temporal", "match_score": float(hits[hits["track_id"] == tid].shape[0]),
            }

        def semantic_match(text):
            if not semantic_ready or not text or not text.strip():
                return None
            emb    = model_sem.encode([text], normalize_embeddings=True)[0]
            scores = moment_embs @ emb
            best_i = int(np.argmax(scores))
            score  = float(scores[best_i])
            if score < 0.15:
                return None
            best_t = library_with_moments[best_i]
            return {
                "track_id": best_t["track_id"], "track_name": best_t["track_name"],
                "artist_name": best_t.get("artist", ""), "album_cover_url": best_t.get("album_cover_url", ""),
                "match_type": "semantic", "match_score": score,
            }

        def best_match(photo_id, ts, caption):
            if photo_id in photo_overrides:
                tid  = photo_overrides[photo_id]
                meta = lib_lookup.get(tid, {})
                return {
                    "track_id": tid,
                    "track_name": meta.get("track_name", tid.replace("spotify:track:", "")),
                    "artist_name": meta.get("artist", ""), "album_cover_url": meta.get("album_cover_url", ""),
                    "match_type": "manual", "match_score": 1.0,
                }
            m = temporal_match(ts)
            if m: return m
            m = semantic_match(caption)
            if m: return m
            m = semantic_match(_time_context(ts))
            if m: return m
            m = temporal_match(ts, window_sec=3 * 3600)
            if m: return m
            return global_fallback or {
                "track_id": None, "track_name": None, "artist_name": None,
                "album_cover_url": "", "match_type": "none", "match_score": 0.0,
            }

        # ── 7. Photo-level matching ───────────────────────────────────────────
        photo_results = []
        for _, row in scenes_pdf.iterrows():
            m = best_match(
                photo_id=row["photo_id"],
                ts=row["exif_date"],
                caption=row.get("caption", "") or "",
            )
            photo_results.append({
                "photo_id":        row["photo_id"],
                "scene_id":        int(row["scene_id"]),
                "path":            row["path"],
                "exif_date":       row["exif_date"],
                "track_id":        m["track_id"],
                "track_name":      m["track_name"],
                "artist_name":     m["artist_name"],
                "album_cover_url": m["album_cover_url"],
                "match_type":      m["match_type"],
                "match_score":     m["match_score"],
            })

        photo_pdf = pd.DataFrame(photo_results)
        print(f"Matching photo terminé : {len(photo_pdf)} photos")
        print(photo_pdf["match_type"].value_counts().to_string())

        # ── 8. Group-level matching ───────────────────────────────────────────
        centroids_pdf = df_centroids.toPandas()
        group_results = []

        for _, row in centroids_pdf.iterrows():
            sid = int(row["scene_id"])
            group_photos = photo_pdf[photo_pdf["scene_id"] == sid]
            strong = group_photos[group_photos["match_type"].isin(["manual", "temporal", "semantic"])]

            if not strong.empty:
                best_tid = strong["track_id"].value_counts().idxmax()
                best_row = strong[strong["track_id"] == best_tid].iloc[0]
                m = {
                    "track_id": best_row["track_id"], "track_name": best_row["track_name"],
                    "artist_name": best_row["artist_name"], "album_cover_url": best_row["album_cover_url"],
                    "match_type": best_row["match_type"],
                    "match_score": float(strong["track_id"].eq(best_tid).sum()),
                }
            else:
                caption = str(row.get("representative_caption", "") or "")
                ts      = row.get("timestamp_start")
                m = best_match(photo_id="__group__", ts=ts, caption=caption)

            group_results.append({
                "scene_id":        sid,
                "scene_name":      row["scene_name"],
                "photo_count":     int(row["photo_count"]),
                "track_id":        m["track_id"],
                "track_name":      m["track_name"],
                "artist_name":     m["artist_name"],
                "album_cover_url": m["album_cover_url"],
                "match_type":      m["match_type"],
                "match_score":     m["match_score"],
                "timestamp_start": row.get("timestamp_start"),
                "timestamp_end":   row.get("timestamp_end"),
            })

        group_pdf = pd.DataFrame(group_results)

        # ── 9. Group playlists ────────────────────────────────────────────────
        playlist_rows = []
        for _, row in centroids_pdf.iterrows():
            sid  = int(row["scene_id"])
            ts0  = row.get("timestamp_start")
            ts1  = row.get("timestamp_end")
            if streams_pdf.empty or ts0 is None or pd.isna(ts0):
                continue
            ts0 = pd.Timestamp(ts0)
            ts1 = pd.Timestamp(ts1) if ts1 and not pd.isna(ts1) else ts0
            window_start = ts0 - pd.Timedelta(seconds=W_SEC)
            window_end   = ts1 + pd.Timedelta(seconds=W_SEC)
            hits = streams_pdf[
                (streams_pdf["stream_ts"] >= window_start) &
                (streams_pdf["stream_ts"] <= window_end)
            ].sort_values("stream_ts")
            for rank, (_, s) in enumerate(hits.iterrows()):
                meta = lib_lookup.get(s["track_id"], {})
                playlist_rows.append({
                    "scene_id":        sid,
                    "scene_name":      row["scene_name"],
                    "rank":            rank,
                    "stream_ts":       s["stream_ts"],
                    "track_id":        s["track_id"],
                    "track_name":      s["track_name"],
                    "artist_name":     s["artist_name"],
                    "album_cover_url": meta.get("album_cover_url", ""),
                })

        playlist_pdf = pd.DataFrame(playlist_rows)
        print(f"Playlist souvenir : {len(playlist_pdf)} entrées")

        # ── 10. Write Delta ───────────────────────────────────────────────────
        (
            spark.createDataFrame(group_pdf.astype({"scene_id": int, "photo_count": int}))
            .write.format("delta").mode("overwrite").save(MATCHES_DIR)
        )
        print(f"✓ music_matches   → {MATCHES_DIR}")

        (
            spark.createDataFrame(photo_pdf.astype({"scene_id": int}))
            .write.format("delta").mode("overwrite").save(PHOTO_MUSIC_DIR)
        )
        print(f"✓ photo_music     → {PHOTO_MUSIC_DIR}")

        if not playlist_pdf.empty:
            (
                spark.createDataFrame(playlist_pdf.astype({"scene_id": int, "rank": int}))
                .write.format("delta").mode("overwrite").save(PLAYLISTS_DIR)
            )
            print(f"✓ group_playlists → {PLAYLISTS_DIR}")
        else:
            print("⚠ Aucune playlist générée")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
