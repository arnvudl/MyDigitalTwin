import sys
import os

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

from config import build_spark_session, PROCESSED_DATA, WAREHOUSE  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql import Window  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    StructType,
    StructField,
    StringType,
    LongType,
    IntegerType,
)
from delta.tables import DeltaTable  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402


SPOTIFY_DIR = os.path.join(PROCESSED_DATA, "SPOTIFY")


def _merge_table(spark, df, table_name: str, merge_condition: str):
    table_path = os.path.join(WAREHOUSE, table_name)
    if DeltaTable.isDeltaTable(spark, table_path):
        DeltaTable.forPath(spark, table_path).alias("t").merge(
            df.alias("s"), merge_condition
        ).whenNotMatchedInsertAll().execute()
    else:
        df.write.format("delta").mode("overwrite").save(table_path)
    count = spark.read.format("delta").load(table_path).count()
    print(f"  ✓ {table_name} — {count:,} lignes")


def parse_streams(spark):
    # Extended history (MyData) + Account data (endsong*.json)
    extended_files = glob.glob(os.path.join(SPOTIFY_DIR, "**", "Streaming_History_Audio_*.json"), recursive=True)
    account_files = glob.glob(os.path.join(SPOTIFY_DIR, "**", "StreamingHistory_music_*.json"), recursive=True)

    all_rows = []
    for path in extended_files + account_files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        source = "extended" if path in extended_files else "account"
        for entry in data:
            ts = entry.get("ts") or entry.get("endTime", "")
            ms = entry.get("ms_played") or entry.get("msPlayed", 0)
            if (ms or 0) < 30000:
                continue
            all_rows.append({
                "ts": ts,
                "ms_played": int(ms or 0),
                "track_name": entry.get("master_metadata_track_name") or entry.get("trackName", ""),
                "artist_name": entry.get("master_metadata_album_artist_name") or entry.get("artistName", ""),
                "album_name": entry.get("master_metadata_album_album_name", ""),
                "platform": entry.get("platform", ""),
                "source": source,
            })

    if not all_rows:
        return None

    schema = StructType([
        StructField("ts", StringType()),
        StructField("ms_played", LongType()),
        StructField("track_name", StringType()),
        StructField("artist_name", StringType()),
        StructField("album_name", StringType()),
        StructField("platform", StringType()),
        StructField("source", StringType()),
    ])
    df = spark.createDataFrame(all_rows, schema=schema)

    # Priority dedup: prefer "extended" source, keep min ms_played row per (track+artist+ts)
    w_priority = Window.partitionBy("track_name", "artist_name", "ts").orderBy(
        F.when(F.col("source") == "extended", 0).otherwise(1),
        F.col("ms_played")
    )
    df = (
        df.withColumn("_priority", F.row_number().over(w_priority))
          .filter(F.col("_priority") == 1)
          .drop("_priority", "source")
    )
    df = (
        df.withColumn("timestamp", F.to_timestamp("ts"))
          .withColumn("event_date", F.to_date("timestamp"))
          .withColumn("event_year", F.year("event_date"))
          .withColumn("event_month", F.month("event_date"))
          .withColumn("event_hour", F.hour("timestamp"))
          .withColumn("event_weekday", F.dayofweek("event_date"))
          .withColumn("data_platform", F.lit("spotify"))
    )
    return df


def parse_liked_songs(spark):
    path = os.path.join(SPOTIFY_DIR, "account", "YourLibrary.json")
    if not os.path.exists(path):
        print("  ⚠ YourLibrary.json introuvable — skip liked songs")
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = [
        {
            "track_name": t.get("track", ""),
            "artist_name": t.get("artist", ""),
            "album_name": t.get("album", ""),
            "uri": t.get("uri", ""),
        }
        for t in data.get("tracks", [])
    ]
    schema = StructType([
        StructField("track_name", StringType()),
        StructField("artist_name", StringType()),
        StructField("album_name", StringType()),
        StructField("uri", StringType()),
    ])
    return spark.createDataFrame(rows, schema=schema)


def parse_playlists(spark):
    path = os.path.join(SPOTIFY_DIR, "account", "Playlist1.json")
    if not os.path.exists(path):
        print("  ⚠ Playlist1.json introuvable — skip playlists")
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for pl in data.get("playlists", []):
        pl_name = pl.get("name", "")
        for item in pl.get("items", []):
            track = item.get("track", {})
            rows.append({
                "playlist_name": pl_name,
                "track_name": track.get("trackName", ""),
                "artist_name": track.get("artistName", ""),
                "album_name": track.get("albumName", ""),
            })
    schema = StructType([
        StructField("playlist_name", StringType()),
        StructField("track_name", StringType()),
        StructField("artist_name", StringType()),
        StructField("album_name", StringType()),
    ])
    return spark.createDataFrame(rows, schema=schema)


def parse_searches(spark):
    path = os.path.join(SPOTIFY_DIR, "account", "SearchQueries.json")
    if not os.path.exists(path):
        print("  ⚠ SearchQueries.json introuvable — skip searches")
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = [
        {
            "query": entry.get("searchQuery", ""),
            "platform": entry.get("platform", ""),
            "ts": entry.get("searchTime", ""),
        }
        for entry in data
        if entry.get("searchQuery")
    ]
    schema = StructType([
        StructField("query", StringType()),
        StructField("platform", StringType()),
        StructField("ts", StringType()),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    return df.withColumn("timestamp", F.to_timestamp("ts")).drop("ts")


def main():
    spark = build_spark_session("MyDigitalTwin - Spotify", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        df = parse_streams(spark)
        if df is not None:
            _merge_table(spark, df, "spotify_streams",
                         "t.track_name = s.track_name AND t.artist_name = s.artist_name AND t.ts = s.ts")

        df = parse_liked_songs(spark)
        if df is not None:
            _merge_table(spark, df, "spotify_liked_songs", "t.uri = s.uri")

        df = parse_playlists(spark)
        if df is not None:
            _merge_table(spark, df, "spotify_playlists",
                         "t.playlist_name = s.playlist_name AND t.track_name = s.track_name AND t.artist_name = s.artist_name")

        df = parse_searches(spark)
        if df is not None:
            _merge_table(spark, df, "spotify_searches", "t.query = s.query")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
