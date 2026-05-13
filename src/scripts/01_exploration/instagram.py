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
from pyspark.sql.types import (  # noqa: E402
    StructType, StructField, StringType, LongType, IntegerType, BooleanType,
)
from delta.tables import DeltaTable  # noqa: E402
import json  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402

IG_ROOT = os.path.join(PROCESSED_DATA, "INSTAGRAM", "your_instagram_activity")


def _find_ig_file(patterns: list) -> str | None:
    for p in patterns:
        matches = glob.glob(p)
        if matches:
            return matches[0]
    return None


def anonymize(val: str, salt: str = "mydigitaltwin") -> str:
    return hashlib.sha256(f"{salt}{val}".encode()).hexdigest()[:10]


# ── 1. Commentaires ───────────────────────────────────────────────────────────

def parse_comments(spark):
    comments_files = glob.glob(f"{IG_ROOT}/comments/post_comments_*.json")
    if not comments_files:
        print("  ⚠ post_comments_*.json introuvable — skip comments")
        return None
    rows = []
    for path in comments_files:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        for item in data:
            smd = item.get("string_map_data", {})
            comment = smd.get("Comment", {}).get("value", "")
            owner = smd.get("Media Owner", {}).get("value", "")
            ts = smd.get("Time", {}).get("timestamp", 0)
            if comment:
                rows.append({"text": comment, "media_owner": owner, "timestamp": ts})
    if not rows:
        return None
    schema = StructType([
        StructField("text", StringType(), True),
        StructField("media_owner", StringType(), True),
        StructField("timestamp", LongType(), True),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    df = (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp")))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
        .withColumn("char_count", F.length("text"))
        .withColumn("word_count", F.size(F.split(F.trim("text"), r"\s+")))
        .withColumn("emoji_count", F.size(F.array_remove(
            F.split(F.regexp_replace("text", r"[\w\s.,!?;:'\"\-()]", " "), " "), ""
        )))
        .withColumn("platform", F.lit("instagram"))
        .withColumn("content_type", F.lit("comment"))
    )
    return df


# ── 2. Likes ──────────────────────────────────────────────────────────────────

def parse_likes(spark):
    likes_path = f"{IG_ROOT}/likes/liked_posts.json"
    if not os.path.exists(likes_path):
        print("  ⚠ liked_posts.json introuvable — skip likes")
        return None
    with open(likes_path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    rows = []
    for item in data:
        ts = item.get("timestamp", 0)
        url = ""
        for lv in item.get("label_values", []):
            if lv.get("label") == "URL":
                url = lv.get("value", lv.get("href", ""))
                break
        rows.append({"timestamp": ts, "post_url": url})
    if not rows:
        return None
    schema = StructType([
        StructField("timestamp", LongType(), True),
        StructField("post_url", StringType(), True),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    df = (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp")))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
        .withColumn("platform", F.lit("instagram"))
        .withColumn("action_type", F.lit("like"))
    )
    return df


# ── 3. Messages (métadonnées) ─────────────────────────────────────────────────

def parse_messages(spark, my_name: str = "arnvudl"):
    inbox_root = f"{IG_ROOT}/messages/inbox"
    msg_files = glob.glob(f"{inbox_root}/*/message_*.json")
    if not msg_files:
        print("  ⚠ messages/inbox introuvable — skip messages")
        return None
    rows = []
    for path in msg_files:
        conv_folder = os.path.basename(os.path.dirname(path))
        conv_id = anonymize(conv_folder)
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        is_group = len(data.get("participants", [])) > 2
        participants = len(data.get("participants", []))
        for msg in data.get("messages", []):
            sender_name = msg.get("sender_name", "")
            ts = msg.get("timestamp_ms", 0)
            content = msg.get("content", "")
            is_unsent = msg.get("is_unsent", False)
            if is_unsent:
                msg_type = "unsent"
            elif msg.get("photos"):
                msg_type = "photo"
            elif msg.get("videos"):
                msg_type = "video"
            elif msg.get("audio_files"):
                msg_type = "audio"
            elif msg.get("share"):
                msg_type = "share"
            elif content:
                msg_type = "text"
            else:
                msg_type = "other"
            rows.append({
                "conv_id": conv_id,
                "is_group": is_group,
                "participants": participants,
                "sender_anon": anonymize(sender_name),
                "timestamp_ms": ts,
                "msg_type": msg_type,
                "char_count": len(content) if content else 0,
            })
    if not rows:
        return None
    schema = StructType([
        StructField("conv_id", StringType(), True),
        StructField("is_group", BooleanType(), True),
        StructField("participants", IntegerType(), True),
        StructField("sender_anon", StringType(), True),
        StructField("timestamp_ms", LongType(), True),
        StructField("msg_type", StringType(), True),
        StructField("char_count", IntegerType(), True),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    df = (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp_ms") / 1000))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
        .withColumn("platform", F.lit("instagram"))
    )
    return df


# ── 4. Saved posts ────────────────────────────────────────────────────────────

def parse_saved(spark):
    saved_path = f"{IG_ROOT}/saved/saved_posts.json"
    if not os.path.exists(saved_path):
        print("  ⚠ saved_posts.json introuvable — skip saved")
        return None
    with open(saved_path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    rows = []
    for item in data.get("saved_saved_media", []):
        title = item.get("title", "")
        saved_on = item.get("string_map_data", {}).get("Saved on", {})
        rows.append({
            "account": title,
            "post_href": saved_on.get("href", ""),
            "timestamp": saved_on.get("timestamp", 0),
        })
    if not rows:
        return None
    schema = StructType([
        StructField("account", StringType(), True),
        StructField("post_href", StringType(), True),
        StructField("timestamp", LongType(), True),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    df = (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp")))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
        .withColumn("platform", F.lit("instagram"))
        .withColumn("action_type", F.lit("saved"))
    )
    return df


# ── 5. Posts vus ──────────────────────────────────────────────────────────────

def parse_posts_viewed(spark):
    ig_ads = os.path.join(os.path.dirname(IG_ROOT), "ads_information", "ads_and_topics")
    path = _find_ig_file([
        f"{IG_ROOT}/ads_and_topics/posts_viewed.json",
        f"{IG_ROOT}/impressions/posts_viewed.json",
        os.path.join(ig_ads, "posts_viewed.json"),
    ])
    if not path:
        print("  ⚠ posts_viewed.json introuvable — skip")
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else (data.get("impressions_history_posts_seen") or [])
    rows = [{"author": "", "timestamp": int(item["timestamp"])} for item in items if item.get("timestamp")]
    if not rows:
        return None
    schema = StructType([
        StructField("author", StringType(), True),
        StructField("timestamp", LongType(), True),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    return (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp")))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
        .withColumn("platform", F.lit("instagram"))
        .withColumn("action_type", F.lit("post_viewed"))
    )


# ── 6. Vidéos regardées ───────────────────────────────────────────────────────

def parse_videos_watched(spark):
    ig_ads = os.path.join(os.path.dirname(IG_ROOT), "ads_information", "ads_and_topics")
    path = _find_ig_file([
        f"{IG_ROOT}/ads_and_topics/videos_watched.json",
        f"{IG_ROOT}/impressions/videos_watched.json",
        os.path.join(ig_ads, "videos_watched.json"),
    ])
    if not path:
        print("  ⚠ videos_watched.json introuvable — skip")
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else (data.get("impressions_history_videos_watched") or [])
    rows = [{"author": "", "timestamp": int(item["timestamp"])} for item in items if item.get("timestamp")]
    if not rows:
        return None
    schema = StructType([
        StructField("author", StringType(), True),
        StructField("timestamp", LongType(), True),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    return (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp")))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
        .withColumn("platform", F.lit("instagram"))
        .withColumn("action_type", F.lit("video_watched"))
    )


# ── 7. Story likes ────────────────────────────────────────────────────────────

def parse_story_likes(spark):
    path = _find_ig_file([
        f"{IG_ROOT}/story_activities/story_likes.json",
        f"{IG_ROOT}/story_interactions/story_likes.json",
        f"{IG_ROOT}/likes/story_likes.json",
        f"{IG_ROOT}/story_likes.json",
    ])
    if not path:
        print("  ⚠ story_likes.json introuvable — skip")
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else (
            data.get("story_activities_story_likes") or data.get("story_likes") or []
    )
    rows = [{"author": "", "timestamp": int(item["timestamp"])} for item in items if item.get("timestamp")]
    if not rows:
        return None
    schema = StructType([
        StructField("author", StringType(), True),
        StructField("timestamp", LongType(), True),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    return (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp")))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
        .withColumn("platform", F.lit("instagram"))
        .withColumn("action_type", F.lit("story_like"))
    )


# ── 8. Recherches ─────────────────────────────────────────────────────────────

def parse_ig_searches(spark):
    ig_logged = os.path.join(os.path.dirname(IG_ROOT), "logged_information", "recent_searches")
    path = _find_ig_file([
        f"{IG_ROOT}/searches/word_or_phrase_searches.json",
        f"{IG_ROOT}/word_or_phrase_searches.json",
        os.path.join(ig_logged, "word_or_phrase_searches.json"),
    ])
    if not path:
        print("  ⚠ word_or_phrase_searches.json introuvable — skip searches")
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    items = data.get("searches_keyword") or data.get("keyword_searches") or (data if isinstance(data, list) else [])
    rows = []
    for item in items:
        smd = item.get("string_map_data", {})
        query = (smd.get("Recherche", {}) or smd.get("Search", {})).get("value", "") or item.get("title", "")
        ts = (smd.get("Heure", {}) or smd.get("Time", {})).get("timestamp", 0)
        if ts and query:
            rows.append({"query": query, "timestamp": int(ts)})
    if not rows:
        return None
    schema = StructType([
        StructField("query", StringType(), True),
        StructField("timestamp", LongType(), True),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    return (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp")))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
        .withColumn("platform", F.lit("instagram"))
        .withColumn("action_type", F.lit("search"))
        .withColumn("char_count", F.length("query"))
        .withColumn("word_count", F.size(F.split(F.trim("query"), r"\s+")))
    )


# ── Write helper ──────────────────────────────────────────────────────────────

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


# ── Main ──────────────────────────────────────────────────────────────────────

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

        df = parse_posts_viewed(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_posts_viewed", "t.timestamp = s.timestamp")

        df = parse_videos_watched(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_videos_watched", "t.timestamp = s.timestamp")

        df = parse_story_likes(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_story_likes", "t.timestamp = s.timestamp")

        df = parse_ig_searches(spark)
        if df is not None:
            _merge_table(spark, df, "instagram_searches", "t.query = s.query AND t.timestamp = s.timestamp")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
