import os
import sys

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

from config import build_spark_session, PROCESSED_DATA, WAREHOUSE  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.window import Window  # noqa: E402
from pyspark.sql.types import StringType, LongType, BooleanType  # noqa: E402
from delta.tables import DeltaTable  # noqa: E402
import glob  # noqa: E402

SPOTIFY_ACCOUNT = os.path.join(PROCESSED_DATA, "SPOTIFY", "account")
SPOTIFY_EXTENDED = os.path.join(PROCESSED_DATA, "SPOTIFY", "extended")

LIBRARY_PATH = os.path.join(SPOTIFY_ACCOUNT, "YourLibrary.json")
PLAYLIST_PATH = os.path.join(SPOTIFY_ACCOUNT, "Playlist1.json")
SEARCH_PATH = os.path.join(SPOTIFY_ACCOUNT, "SearchQueries.json")

OUT_STREAMS = os.path.join(WAREHOUSE, "spotify_streams")
OUT_LIKED_SONGS = os.path.join(WAREHOUSE, "spotify_liked_songs")
OUT_PLAYLISTS = os.path.join(WAREHOUSE, "spotify_playlists")
OUT_SEARCHES = os.path.join(WAREHOUSE, "spotify_searches")


def _merge_or_create(spark, df, path: str, condition: str):
    if DeltaTable.isDeltaTable(spark, path):
        DeltaTable.forPath(spark, path).alias("t").merge(
            df.alias("s"), condition
        ).whenNotMatchedInsertAll().execute()
    else:
        df.write.format("delta").save(path)
    count = spark.read.format("delta").load(path).count()
    print(f"  ✓ {os.path.basename(path)} — {count:,} lignes")


def main():
    spark = build_spark_session("MyDigitalTwin - Spotify", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        extended_files = sorted(glob.glob(os.path.join(SPOTIFY_EXTENDED, "Streaming_History_Audio_*.json")))
        account_files = sorted(glob.glob(os.path.join(SPOTIFY_ACCOUNT, "StreamingHistory_music_*.json")))
        print(f"  Extended: {len(extended_files)} fichiers, Account: {len(account_files)} fichiers")

        # ── Extended History ──────────────────────────────────────────────────
        df_ext = (
            spark.read.option("multiLine", "true").json(extended_files)
            .filter(F.col("master_metadata_track_name").isNotNull())
            .select(
                F.to_timestamp(F.col("ts"), "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("listen_ts"),
                F.col("master_metadata_album_artist_name").alias("artistName"),
                F.col("master_metadata_track_name").alias("trackName"),
                F.col("ms_played").cast(LongType()).alias("msPlayed"),
                F.col("spotify_track_uri").alias("trackUri"),
                F.col("skipped").cast(BooleanType()).alias("skipped"),
                F.col("shuffle").cast(BooleanType()).alias("shuffle"),
                F.lit("extended").alias("_source"),
            )
            .filter(F.col("listen_ts").isNotNull())
        )

        # ── Account Data ──────────────────────────────────────────────────────
        df_acc = (
            spark.read.option("multiLine", "true").json(account_files)
            .filter(F.col("trackName").isNotNull())
            .select(
                F.to_timestamp(F.col("endTime"), "yyyy-MM-dd HH:mm").alias("listen_ts"),
                F.col("artistName"),
                F.col("trackName"),
                F.col("msPlayed").cast(LongType()),
                F.lit(None).cast(StringType()).alias("trackUri"),
                F.lit(None).cast(BooleanType()).alias("skipped"),
                F.lit(None).cast(BooleanType()).alias("shuffle"),
                F.lit("account").alias("_source"),
            )
            .filter(F.col("listen_ts").isNotNull())
        )

        # ── Fusion & Déduplication ────────────────────────────────────────────
        df_all = df_ext.union(df_acc)
        df_all = df_all \
            .withColumn("_dedup_min", F.date_format(F.date_trunc("minute", F.col("listen_ts")), "yyyy-MM-dd HH:mm")) \
            .withColumn("_priority", F.when(F.col("_source") == "extended", 0).otherwise(1))

        w = Window.partitionBy("artistName", "trackName", "_dedup_min").orderBy("_priority")
        df_merged = df_all \
            .withColumn("_rn", F.row_number().over(w)) \
            .filter(F.col("_rn") == 1) \
            .drop("_rn", "_source", "_dedup_min", "_priority")

        # ── Nettoyage & Features ──────────────────────────────────────────────
        df_streams = df_merged.filter(F.col("msPlayed") >= 30000)
        df_streams = df_streams \
            .withColumn("listen_year", F.year("listen_ts")) \
            .withColumn("listen_month", F.date_format("listen_ts", "yyyy-MM")) \
            .withColumn("listen_hour", F.hour("listen_ts")) \
            .withColumn("listen_weekday", F.dayofweek("listen_ts")) \
            .withColumn("listen_week", F.weekofyear("listen_ts")) \
            .withColumn("minutes_played", F.round(F.col("msPlayed") / 60000.0, 2)) \
            .withColumn("is_night", F.when(
            (F.col("listen_hour") >= 22) | (F.col("listen_hour") <= 5), True
        ).otherwise(False))

        df_streams_final = df_streams.select(
            "artistName", "trackName", "msPlayed", "minutes_played",
            "trackUri", "skipped", "shuffle", "listen_ts",
            "listen_year", "listen_month", "listen_hour",
            "listen_weekday", "listen_week", "is_night",
        )

        _merge_or_create(spark, df_streams_final, OUT_STREAMS,
                         "t.artistName = s.artistName AND t.trackName = s.trackName "
                         "AND date_trunc('minute', t.listen_ts) = date_trunc('minute', s.listen_ts)")

        # ── YourLibrary — titres likés ────────────────────────────────────────
        if os.path.exists(LIBRARY_PATH):
            df_liked = (
                spark.read.option("multiLine", "true").json(LIBRARY_PATH)
                .select(F.explode("tracks").alias("t"))
                .select(
                    F.col("t.artist").alias("artistName"),
                    F.col("t.album").alias("albumName"),
                    F.col("t.track").alias("trackName"),
                    F.col("t.uri").alias("trackUri"),
                )
                .filter(F.col("trackName").isNotNull())
            )
            _merge_or_create(spark, df_liked, OUT_LIKED_SONGS, "t.trackUri = s.trackUri")
        else:
            print("  ⚠ YourLibrary.json introuvable — skip")

        # ── Playlists ─────────────────────────────────────────────────────────
        if os.path.exists(PLAYLIST_PATH):
            df_playlists = (
                spark.read.option("multiLine", "true").json(PLAYLIST_PATH)
                .select(F.explode("playlists").alias("pl"))
                .select(
                    F.col("pl.name").alias("playlistName"),
                    F.col("pl.lastModifiedDate").alias("lastModifiedDate"),
                    F.explode("pl.items").alias("item"),
                )
                .select(
                    F.col("playlistName"),
                    F.col("lastModifiedDate"),
                    F.col("item.track.trackName").alias("trackName"),
                    F.col("item.track.artistName").alias("artistName"),
                    F.col("item.track.albumName").alias("albumName"),
                    F.col("item.track.trackUri").alias("trackUri"),
                    F.to_date(F.col("item.addedDate"), "yyyy-MM-dd").alias("addedDate"),
                )
                .filter(F.col("trackName").isNotNull())
            )
            _merge_or_create(spark, df_playlists, OUT_PLAYLISTS,
                             "t.playlistName = s.playlistName AND t.trackUri = s.trackUri AND t.addedDate = s.addedDate")
        else:
            print("  ⚠ Playlist1.json introuvable — skip")

        # ── Recherches ────────────────────────────────────────────────────────
        if os.path.exists(SEARCH_PATH):
            df_searches = (
                spark.read.option("multiLine", "true").json(SEARCH_PATH)
                .filter(F.col("searchQuery").isNotNull() & (F.length(F.col("searchQuery")) > 0))
                .select(
                    F.to_timestamp(
                        F.regexp_replace(F.col("searchTime"), r"\[UTC\]$", ""),
                        "yyyy-MM-dd'T'HH:mm:ss.SSSX"
                    ).alias("search_ts"),
                    F.trim(F.col("searchQuery")).alias("query"),
                    F.col("platform"),
                )
                .filter(F.col("search_ts").isNotNull())
                .withColumn("event_hour", F.hour("search_ts"))
                .withColumn("event_weekday", F.dayofweek("search_ts"))
            )
            _merge_or_create(spark, df_searches, OUT_SEARCHES,
                             "t.query = s.query AND t.search_ts = s.search_ts")
        else:
            print("  ⚠ SearchQueries.json introuvable — skip")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
