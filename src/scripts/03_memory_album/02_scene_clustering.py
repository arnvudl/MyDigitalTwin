import sys
import os

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

import yaml  # noqa: E402
import re  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from delta.tables import DeltaTable  # noqa: E402
from config import build_spark_session, MEMORY_ALBUM_DIR  # noqa: E402


EMBEDDINGS_DIR = os.path.join(MEMORY_ALBUM_DIR, "photo_embeddings")
SCENES_DIR     = os.path.join(MEMORY_ALBUM_DIR, "scenes")
CENTROIDS_DIR  = os.path.join(MEMORY_ALBUM_DIR, "scene_centroids")

MONTH_FR = ["jan", "fév", "mar", "avr", "mai", "juin",
            "juil", "août", "sep", "oct", "nov", "déc"]

_DATE_PATTERNS = [
    (r"(\d{8})_(\d{6})",        "compact8_6"),
    (r"(\d{4})-(\d{2})-(\d{2})", "iso"),
    (r"(?<!\d)(\d{8})(?!\d)",   "compact8"),
]


def time_slot(dt) -> str:
    h = dt.hour
    if   6  <= h < 12: return "Matin"
    elif 12 <= h < 18: return "Après-midi"
    elif 18 <= h < 23: return "Soirée"
    else:              return "Nuit"


def group_label(dt) -> str:
    return f"{time_slot(dt)} · {dt.day} {MONTH_FR[dt.month-1]} {dt.year}"


def _date_from_filename(filename: str):
    base = os.path.basename(filename)
    for pat, kind in _DATE_PATTERNS:
        m = re.search(pat, base)
        if not m:
            continue
        try:
            g = m.groups()
            if kind == "compact8_6":
                raw = g[0]
                y, mo, d = int(raw[:4]), int(raw[4:6]), int(raw[6:8])
            elif kind == "iso":
                y, mo, d = int(g[0]), int(g[1]), int(g[2])
            else:
                raw = g[0]
                y, mo, d = int(raw[:4]), int(raw[4:6]), int(raw[6:8])
            if 2000 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
                return pd.Timestamp(y, mo, d, 12, 0, 0)
        except Exception:
            continue
    return None


def main():
    cfg_path = os.path.join(_d, "config.yaml")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    ma = cfg.get("memory_album", {})
    gap_hours = float(ma.get("scene_gap_hours", 6.0))
    gap_sec   = gap_hours * 3600
    print(f"Seuil gap temporel : {gap_hours}h")

    spark = build_spark_session(
        "MyDigitalTwin-MemoryAlbum-Clustering",
        driver_memory="4g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        # ── 3. Load embeddings ────────────────────────────────────────────────
        if DeltaTable.isDeltaTable(spark, EMBEDDINGS_DIR):
            df = spark.read.format("delta").load(EMBEDDINGS_DIR)
        else:
            df = spark.read.parquet(EMBEDDINGS_DIR)

        print(f"{df.count()} photos chargées")

        rows = df.select(
            "photo_id", "path", "filename", "exif_date",
            "lat", "lon", "caption", "embedding", "has_gps"
        ).toPandas()

        rows["exif_date"] = pd.to_datetime(rows["exif_date"], errors="coerce")
        rows["caption"]   = rows["caption"].fillna("")

        n_dated   = rows["exif_date"].notna().sum()
        n_undated = rows["exif_date"].isna().sum()
        print(f"Avec date EXIF : {n_dated} | Sans date : {n_undated}")

        # ── 4. Temporal grouping ──────────────────────────────────────────────
        dated   = rows[rows["exif_date"].notna()].sort_values("exif_date").copy()
        undated = rows[rows["exif_date"].isna()].copy()

        groups = []
        current = []

        for idx, row in dated.iterrows():
            if not current:
                current.append(idx)
            else:
                prev_dt = rows.loc[current[-1], "exif_date"]
                gap = (row["exif_date"] - prev_dt).total_seconds()
                if gap > gap_sec:
                    groups.append(current)
                    current = [idx]
                else:
                    current.append(idx)
        if current:
            groups.append(current)

        rows["scene_id"]   = -1
        rows["scene_name"] = ""

        for gid, grp_indices in enumerate(groups):
            first_dt = rows.loc[grp_indices[0], "exif_date"]
            name = group_label(first_dt)
            rows.loc[grp_indices, "scene_id"]   = gid
            rows.loc[grp_indices, "scene_name"] = name

        print(f"{len(groups)} groupes temporels créés")

        # ── 5. Undated photo attachment ───────────────────────────────────────
        if len(undated) == 0:
            print("Toutes les photos ont une date EXIF — rien à rattacher")
        elif len(groups) == 0:
            rows.loc[undated.index, "scene_id"]   = 0
            rows.loc[undated.index, "scene_name"] = "Moment sans date"
        else:
            group_centroids = {}
            for gid, grp_indices in enumerate(groups):
                embs = np.stack([
                    np.array(rows.loc[i, "embedding"], dtype=np.float32)
                    for i in grp_indices
                ])
                c = embs.mean(axis=0)
                group_centroids[gid] = c / (np.linalg.norm(c) + 1e-8)

            centroids_matrix = np.stack(
                [group_centroids[i] for i in range(len(groups))]
            )

            group_mids = []
            for gid, grp_indices in enumerate(groups):
                t0 = rows.loc[grp_indices[0],  "exif_date"]
                t1 = rows.loc[grp_indices[-1], "exif_date"]
                group_mids.append(t0 + (t1 - t0) / 2)

            VISUAL_THRESHOLD = 0.60
            by_filename = by_visual = to_undated = 0

            for idx in undated.index:
                path_val = str(rows.loc[idx, "path"] or "")
                fn_val   = str(rows.loc[idx, "filename"] or path_val)
                assigned = False

                fn_date = _date_from_filename(fn_val) or _date_from_filename(path_val)
                if fn_date is not None:
                    deltas = [abs((fn_date - mid).total_seconds()) for mid in group_mids]
                    nearest_gid = int(np.argmin(deltas))
                    rows.loc[idx, "scene_id"]   = nearest_gid
                    rows.loc[idx, "scene_name"] = rows.loc[groups[nearest_gid][0], "scene_name"]
                    by_filename += 1
                    assigned = True

                if not assigned:
                    emb   = np.array(rows.loc[idx, "embedding"], dtype=np.float32)
                    emb_n = emb / (np.linalg.norm(emb) + 1e-8)
                    sims  = centroids_matrix @ emb_n
                    best  = int(np.argmax(sims))
                    best_sim = float(sims[best])

                    if best_sim >= VISUAL_THRESHOLD:
                        rows.loc[idx, "scene_id"]   = best
                        rows.loc[idx, "scene_name"] = rows.loc[groups[best][0], "scene_name"]
                        by_visual += 1
                        assigned = True

                if not assigned:
                    rows.loc[idx, "scene_id"]   = -2
                    rows.loc[idx, "scene_name"] = "Moment sans date"
                    to_undated += 1

            if (rows["scene_id"] == -2).any():
                undated_sid = int(rows[rows["scene_id"] >= 0]["scene_id"].max()) + 1
                rows.loc[rows["scene_id"] == -2, "scene_id"] = undated_sid
                print(f"Nouveau groupe [scene_id={undated_sid}] créé pour les photos sans date")

            print(f"\n{len(undated)} photos sans date rattachées :")
            print(f"  {by_filename:2d}  par date dans le nom de fichier")
            print(f"  {by_visual:2d}  par similarité visuelle (seuil {VISUAL_THRESHOLD})")
            print(f"  {to_undated:2d}  → groupe 'Moment sans date'")

        # ── 6. Final recap ────────────────────────────────────────────────────
        rows["scene_id"] = rows["scene_id"].astype(int)
        rows["is_noise"] = False

        # ── 7. Write scenes (Delta MERGE) ─────────────────────────────────────
        df_scenes = spark.createDataFrame(
            rows[["photo_id", "path", "filename", "exif_date",
                  "lat", "lon", "caption", "scene_id", "scene_name", "is_noise"]]
            .astype({"scene_id": int})
            .where(rows["path"].notna())
        )

        if DeltaTable.isDeltaTable(spark, SCENES_DIR):
            (
                DeltaTable.forPath(spark, SCENES_DIR).alias("target")
                .merge(df_scenes.alias("source"), "target.photo_id = source.photo_id")
                .whenMatchedUpdateAll()
                .whenNotMatchedInsertAll()
                .execute()
            )
        else:
            df_scenes.write.format("delta").mode("overwrite").save(SCENES_DIR)

        print(f"Table scenes --> {SCENES_DIR}")

        # ── 8. Write centroids (Delta MERGE) ──────────────────────────────────
        centroids_rows = []
        for sid in sorted(rows["scene_id"].unique()):
            mask   = rows["scene_id"] == sid
            subset = rows[mask]

            embs     = np.stack(subset["embedding"].apply(
                lambda e: np.array(e, dtype=np.float32)
            ).values)
            centroid = embs.mean(axis=0)

            norms   = np.linalg.norm(embs - centroid, axis=1)
            rep_idx = subset.index[np.argmin(norms)]

            dates  = subset["exif_date"].dropna()
            ts_min = dates.min() if len(dates) else None
            ts_max = dates.max() if len(dates) else None

            centroids_rows.append({
                "scene_id":               int(sid),
                "scene_name":             subset["scene_name"].iloc[0],
                "photo_count":            int(mask.sum()),
                "centroid_embedding":     centroid.tolist(),
                "representative_caption": rows.loc[rep_idx, "caption"],
                "representative_photo":   rows.loc[rep_idx, "path"],
                "timestamp_start":        ts_min,
                "timestamp_end":          ts_max,
                "photo_ids":              subset["photo_id"].tolist(),
            })

        df_centroids = spark.createDataFrame(pd.DataFrame(centroids_rows))

        if DeltaTable.isDeltaTable(spark, CENTROIDS_DIR):
            (
                DeltaTable.forPath(spark, CENTROIDS_DIR).alias("target")
                .merge(df_centroids.alias("source"), "target.scene_id = source.scene_id")
                .whenMatchedUpdateAll()
                .whenNotMatchedInsertAll()
                .execute()
            )
        else:
            df_centroids.write.format("delta").mode("overwrite").save(CENTROIDS_DIR)

        print(f"Table centroids --> {CENTROIDS_DIR}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
