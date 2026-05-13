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
from pyspark.sql.types import (  # noqa: E402
    StructType,
    StructField,
    StringType,
    LongType,
    IntegerType,
)
from delta.tables import DeltaTable  # noqa: E402
import json  # noqa: E402
import glob  # noqa: E402


INSTAGRAM_DIR = os.path.join(PROCESSED_DATA, "INSTAGRAM")


def _find_ig_file(pattern: str) -> str | None:
    matches = glob.glob(os.path.join(INSTAGRAM_DIR, "**", pattern), recursive=True)
    return matches[0] if matches else None


def _label_value(label_values: list, label: str, field: str = "href") -> str:
    """Extract a field from a label_values list by label name."""
    for lv in label_values:
        if lv.get("label") == label:
            return lv.get(field) or lv.get("value") or lv.get("href") or ""
    return ""


def parse_comments(spark):
    path = _find_ig_file("post_comments_1.json")
    if not path:
        print("  ⚠ post_comments_1.json introuvable — skip comments")
        return None
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    rows = []
    for entry in raw:
        smd = entry.get("string_map_data", {})
        rows.append({
            "text": smd.get("Comment", {}).get("value", ""),
            "media_owner": smd.get("Media Owner", {}).get("value", ""),
            "timestamp": smd.get("Time", {}).get("timestamp", 0),
        })
    if not rows:
        return None
    schema = StructType([
        StructField("text", StringType()),
        StructField("media_owner", StringType()),
        StructField("timestamp", LongType()),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    df = (
        df.withColumn("event_date", F.to_date(F.from_unixtime("timestamp")))
          .withColumn("event_year", F.year("event_date"))
          .withColumn("event_month", F.month("event_date"))
          .withColumn("event_hour", F.hour(F.from_unixtime("timestamp")))
          .withColumn("event_weekday", F.dayofweek("event_date"))
          .withColumn("char_count", F.length("text"))
          .withColumn("word_count", F.size(F.split(F.trim("text"), r"\s+")))
          .withColumn("platform", F.lit("instagram"))
          .withColumn("content_type", F.lit("comment"))
    )
    return df


def parse_likes(spark):
    # liked_posts.json is a plain list: [{timestamp, label_values: [{label, value, href}]}]
    path = _find_ig_file("liked_posts.json")
    if not path:
        print("  ⚠ liked_posts.json introuvable — skip likes")
        return None
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    rows = []
    for entry in raw:
        url = _label_value(entry.get("label_values", []), "URL", "href")
        rows.append({
            "timestamp": entry.get("timestamp", 0),
            "post_url": url,
        })
    if not rows:
        return None
    schema = StructType([
        StructField("timestamp", LongType()),
        StructField("post_url", StringType()),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    df = (
        df.withColumn("event_date", F.to_date(F.from_unixtime("timestamp")))
          .withColumn("event_year", F.year("event_date"))
          .withColumn("event_month", F.month("event_date"))
          .withColumn("event_hour", F.hour(F.from_unixtime("timestamp")))
          .withColumn("event_weekday", F.dayofweek("event_date"))
          .withColumn("platform", F.lit("instagram"))
          .withColumn("action_type", F.lit("like"))
    )
    return df


def parse_messages(spark, my_name: str = "A R N A U D"):
    msg_dir = os.path.join(INSTAGRAM_DIR, "messages", "inbox")
    if not os.path.isdir(msg_dir):
        print("  ⚠ messages/inbox introuvable — skip messages")
        return None
    rows = []
    for convo_dir in os.listdir(msg_dir):
        convo_path = os.path.join(msg_dir, convo_dir)
        if not os.path.isdir(convo_path):
            continue
        for fname in glob.glob(os.path.join(convo_path, "message_*.json")):
            with open(fname, encoding="utf-8") as f:
                data = json.load(f)
            participants = [p["name"] for p in data.get("participants", [])]
            is_group = len(participants) > 2
            conv_id = data.get("thread_path", convo_dir)
            for msg in data.get("messages", []):
                sender = msg.get("sender_name", "")
                sender_anon = "me" if sender == my_name else "other"
                rows.append({
                    "conv_id": conv_id,
                    "is_group": is_group,
                    "participants": ",".join(participants),
                    "sender_anon": sender_anon,
                    "timestamp_ms": msg.get("timestamp_ms", 0),
                    "msg_type": msg.get("type", "Generic"),
                    "char_count": len(msg.get("content", "")),
                })
    if not rows:
        return None
    schema = StructType([
        StructField("conv_id", StringType()),
        StructField("is_group", StringType()),
        StructField("participants", StringType()),
        StructField("sender_anon", StringType()),
        StructField("timestamp_ms", LongType()),
        StructField("msg_type", StringType()),
        StructField("char_count", IntegerType()),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    df = (
        df.withColumn("event_date", F.to_date(F.from_unixtime(F.col("timestamp_ms") / 1000)))
          .withColumn("event_year", F.year("event_date"))
          .withColumn("event_month", F.month("event_date"))
          .withColumn("event_hour", F.hour(F.from_unixtime(F.col("timestamp_ms") / 1000)))
          .withColumn("event_weekday", F.dayofweek("event_date"))
          .withColumn("platform", F.lit("instagram"))
    )
    return df


def parse_saved(spark):
    path = _find_ig_file("saved_posts.json")
    if not path:
        print("  ⚠ saved_posts.json introuvable — skip saved")
        return None
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    rows = []
    for entry in raw.get("saved_saved_media", []):
        smd = entry.get("string_map_data", {})
        saved_on = smd.get("Saved on", {})
        rows.append({
            "post_href": saved_on.get("href", ""),
            "timestamp": saved_on.get("timestamp", 0),
        })
    if not rows:
        return None
    schema = StructType([
        StructField("post_href", StringType()),
        StructField("timestamp", LongType()),
    ])
    return spark.createDataFrame(rows, schema=schema)


def parse_timestamp_list(spark, filename: str) -> object:
    """Parse files that are plain lists: [{timestamp, label_values, ...}]"""
    path = _find_ig_file(filename)
    if not path:
        print(f"  ⚠ {filename} introuvable — skip")
        return None
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    rows = []
    if isinstance(raw, list):
        for entry in raw:
            rows.append({"timestamp": entry.get("timestamp", 0)})
    if not rows:
        return None
    schema = StructType([StructField("timestamp", LongType())])
    return spark.createDataFrame(rows, schema=schema)


def parse_ig_searches(spark):
    path = _find_ig_file("profile_searches.json")
    if not path:
        print("  ⚠ profile_searches.json introuvable — skip searches")
        return None
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    rows = []
    for entry in raw.get("searches_user", []):
        for val in entry.get("string_list_data", []):
            rows.append({
                "query": entry.get("title", ""),
                "timestamp": val.get("timestamp", 0),
            })
    if not rows:
        return None
    schema = StructType([
        StructField("query", StringType()),
        StructField("timestamp", LongType()),
    ])
    return spark.createDataFrame(rows, schema=schema)


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


def main():
    spark = build_spark_session("MyDigitalTwin - Instagram", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        df = parse_comments(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_comments", "t.text = s.text AND t.timestamp = s.timestamp")

        df = parse_likes(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_likes", "t.post_url = s.post_url AND t.timestamp = s.timestamp")

        df = parse_messages(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_messages_meta",
                         "t.conv_id = s.conv_id AND t.sender_anon = s.sender_anon AND t.timestamp_ms = s.timestamp_ms AND t.msg_type = s.msg_type")

        df = parse_saved(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_saved", "t.post_href = s.post_href AND t.timestamp = s.timestamp")

        df = parse_timestamp_list(spark, "posts_viewed.json")
        if df is not None:
            _merge_table(spark, df, "instagram_posts_viewed", "t.timestamp = s.timestamp")

        df = parse_timestamp_list(spark, "videos_watched.json")
        if df is not None:
            _merge_table(spark, df, "instagram_videos_watched", "t.timestamp = s.timestamp")

        df = parse_timestamp_list(spark, "story_likes.json")
        if df is not None:
            _merge_table(spark, df, "instagram_story_likes", "t.timestamp = s.timestamp")

        df = parse_ig_searches(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_searches", "t.query = s.query AND t.timestamp = s.timestamp")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
