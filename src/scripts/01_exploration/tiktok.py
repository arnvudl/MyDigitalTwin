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
import hashlib  # noqa: E402
import re  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

RAW_PATH = os.path.join(PROCESSED_DATA, "TIKTOK", "user_data_tiktok.json")
MY_USERNAME = "arnvudl"


def anonymize(val: str, salt: str = "mydigitaltwin") -> str:
    return hashlib.sha256(f"{salt}{val}".encode()).hexdigest()[:10]


def parse_dt(date_str: str) -> int:
    if not date_str:
        return 0
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S")
        return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    except Exception:
        return 0


def extract_video_id(url: str) -> str:
    m = re.search(r"video/(\d+)", url or "")
    return m.group(1) if m else ""


def _merge_or_create(spark, df, table_name: str, condition: str):
    path = os.path.join(WAREHOUSE, table_name)
    if DeltaTable.isDeltaTable(spark, path):
        DeltaTable.forPath(spark, path).alias("t").merge(
            df.alias("s"), condition
        ).whenNotMatchedInsertAll().execute()
    else:
        df.write.format("delta").save(path)
    count = spark.read.format("delta").load(path).count()
    print(f"  ✓ {table_name} — {count:,} lignes")


def _ts_cols(df):
    return (
        df.withColumn("event_date", F.to_timestamp(F.col("timestamp_ms") / 1000))
        .withColumn("event_year", F.year("event_date"))
        .withColumn("event_month", F.date_format("event_date", "yyyy-MM"))
        .withColumn("event_hour", F.hour("event_date"))
        .withColumn("event_weekday", F.dayofweek("event_date"))
    )


def main():
    spark = build_spark_session("MyDigitalTwin - TikTok", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        if not os.path.exists(RAW_PATH):
            print(f"  ⚠ user_data_tiktok.json introuvable — skip tiktok")
            return

        print("  Chargement du JSON TikTok...")
        with open(RAW_PATH, encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        schema_action = StructType([
            StructField("video_id", StringType(), True),
            StructField("url", StringType(), True),
            StructField("timestamp_ms", LongType(), True),
            StructField("action_type", StringType(), True),
            StructField("platform", StringType(), True),
        ])

        # ── 1. Watch History ─────────────────────────────────────────────────
        raw_watch = data.get("Your Activity", {}).get("Watch History", {}).get("VideoList", [])
        watch_rows = [
            {
                "video_id": extract_video_id(item.get("Link", "")),
                "url": item.get("Link", ""),
                "timestamp_ms": parse_dt(item.get("Date", "")),
                "action_type": "watch",
                "platform": "tiktok",
            }
            for item in raw_watch
        ]
        if watch_rows:
            df_watch = _ts_cols(spark.createDataFrame(watch_rows, schema=schema_action))
            _merge_or_create(spark, df_watch, "tiktok_watch",
                             "t.video_id = s.video_id AND t.timestamp_ms = s.timestamp_ms")

        # ── 2. Likes ─────────────────────────────────────────────────────────
        raw_likes = data.get("Likes and Favorites", {}).get("Like List", {}).get("ItemFavoriteList", [])
        like_rows = [
            {
                "video_id": extract_video_id(item.get("link", "")),
                "url": item.get("link", ""),
                "timestamp_ms": parse_dt(item.get("date", "")),
                "action_type": "like",
                "platform": "tiktok",
            }
            for item in raw_likes
        ]
        if like_rows:
            df_likes = _ts_cols(spark.createDataFrame(like_rows, schema=schema_action))
            _merge_or_create(spark, df_likes, "tiktok_likes",
                             "t.video_id = s.video_id AND t.timestamp_ms = s.timestamp_ms")

        # ── 2B. Saves ────────────────────────────────────────────────────────
        raw_saves = data.get("Likes and Favorites", {}).get("Favorite Videos", {}).get("FavoriteVideoList", [])
        save_rows = [
            {
                "video_id": extract_video_id(item.get("Link", "")),
                "url": item.get("Link", ""),
                "timestamp_ms": parse_dt(item.get("Date", "")),
                "action_type": "save",
                "platform": "tiktok",
            }
            for item in raw_saves
        ]
        if save_rows:
            df_saves = _ts_cols(spark.createDataFrame(save_rows, schema=schema_action))
            _merge_or_create(spark, df_saves, "tiktok_saves",
                             "t.video_id = s.video_id AND t.timestamp_ms = s.timestamp_ms")

        # ── 3. Recherches ────────────────────────────────────────────────────
        raw_searches = data.get("Your Activity", {}).get("Searches", {}).get("SearchList", [])
        schema_search = StructType([
            StructField("query", StringType(), True),
            StructField("timestamp_ms", LongType(), True),
            StructField("char_count", IntegerType(), True),
            StructField("word_count", IntegerType(), True),
            StructField("platform", StringType(), True),
        ])
        search_rows = [
            {
                "query": item.get("SearchTerm", ""),
                "timestamp_ms": parse_dt(item.get("Date", "")),
                "char_count": len(item.get("SearchTerm", "")),
                "word_count": len(item.get("SearchTerm", "").split()),
                "platform": "tiktok",
            }
            for item in raw_searches
        ]
        if search_rows:
            df_searches = _ts_cols(spark.createDataFrame(search_rows, schema=schema_search))
            _merge_or_create(spark, df_searches, "tiktok_searches",
                             "t.query = s.query AND t.timestamp_ms = s.timestamp_ms")

        # ── 4. Commentaires ──────────────────────────────────────────────────
        raw_comments = data.get("Comment", {}).get("Comments", {}).get("CommentsList", [])
        schema_comments = StructType([
            StructField("text", StringType(), True),
            StructField("url", StringType(), True),
            StructField("timestamp_ms", LongType(), True),
            StructField("char_count", IntegerType(), True),
            StructField("word_count", IntegerType(), True),
            StructField("platform", StringType(), True),
            StructField("content_type", StringType(), True),
        ])
        comment_rows = [
            {
                "text": item.get("comment", ""),
                "url": item.get("url", ""),
                "timestamp_ms": parse_dt(item.get("date", "")),
                "char_count": len(item.get("comment", "")),
                "word_count": len(item.get("comment", "").split()),
                "platform": "tiktok",
                "content_type": "comment",
            }
            for item in raw_comments
        ]
        if comment_rows:
            df_comments = _ts_cols(spark.createDataFrame(comment_rows, schema=schema_comments))
            _merge_or_create(spark, df_comments, "tiktok_comments",
                             "t.text = s.text AND t.timestamp_ms = s.timestamp_ms")

        # ── 5. Messages ──────────────────────────────────────────────────────
        chat_history = data.get("Direct Message", {}).get("Direct Messages", {}).get("ChatHistory", {})
        schema_meta = StructType([
            StructField("conv_id", StringType(), True),
            StructField("sender_anon", StringType(), True),
            StructField("is_me", BooleanType(), True),
            StructField("timestamp_ms", LongType(), True),
            StructField("msg_type", StringType(), True),
            StructField("char_count", IntegerType(), True),
            StructField("platform", StringType(), True),
        ])
        schema_text = StructType([
            StructField("text", StringType(), True),
            StructField("timestamp_ms", LongType(), True),
            StructField("platform", StringType(), True),
            StructField("content_type", StringType(), True),
        ])
        meta_rows = []
        text_rows = []
        for conv_key, messages in chat_history.items():
            conv_id = anonymize(conv_key)
            if not isinstance(messages, list):
                continue
            for msg in messages:
                ts_ms = parse_dt(msg.get("Date", ""))
                sender = msg.get("From", "")
                content = msg.get("Content", "")
                is_me = sender == MY_USERNAME
                has_url = content.startswith("http") if content else False
                msg_type = "url" if has_url else ("text" if content else "other")
                meta_rows.append({
                    "conv_id": conv_id,
                    "sender_anon": anonymize(sender),
                    "is_me": is_me,
                    "timestamp_ms": ts_ms,
                    "msg_type": msg_type,
                    "char_count": len(content) if content else 0,
                    "platform": "tiktok",
                })
                if is_me and content and not has_url:
                    text_rows.append({
                        "text": content,
                        "timestamp_ms": ts_ms,
                        "platform": "tiktok",
                        "content_type": "dm",
                    })
        if meta_rows:
            df_meta = _ts_cols(spark.createDataFrame(meta_rows, schema=schema_meta))
            _merge_or_create(spark, df_meta, "tiktok_messages_meta",
                             "t.conv_id = s.conv_id AND t.sender_anon = s.sender_anon AND t.timestamp_ms = s.timestamp_ms")
        if text_rows:
            df_text = spark.createDataFrame(text_rows, schema=schema_text) \
                .withColumn("event_date", F.to_timestamp(F.col("timestamp_ms") / 1000)) \
                .withColumn("char_count", F.length("text")) \
                .withColumn("word_count", F.size(F.split(F.trim("text"), r"\s+")))
            _merge_or_create(spark, df_text, "tiktok_messages_text",
                             "t.text = s.text AND t.timestamp_ms = s.timestamp_ms")

        # ── 6. Hashtags favoris ──────────────────────────────────────────────
        fav_hashtags = data.get("Likes and Favorites", {}).get("Favorite Hashtags", {}).get("FavoriteHashtagList", [])
        ht_rows = [
            {"hashtag": ht.get("HashtagName", "") or ht.get("hashtag", ""), "platform": "tiktok"}
            for ht in fav_hashtags
            if ht.get("HashtagName") or ht.get("hashtag")
        ]
        if ht_rows:
            schema_ht = StructType(
                [StructField("hashtag", StringType(), True), StructField("platform", StringType(), True)])
            df_ht = spark.createDataFrame(ht_rows, schema=schema_ht)
            _merge_or_create(spark, df_ht, "tiktok_favorite_hashtags", "t.hashtag = s.hashtag")

        # ── 7. Centres d'intérêt publicitaires ──────────────────────────────
        ads_raw = data.get("Ads", {}).get("Interests", [])
        if isinstance(ads_raw, dict):
            ads_raw = ads_raw.get("adInterestCategories", [])
        ai_rows = []
        for item in ads_raw:
            cat = item if isinstance(item, str) else (item.get("Name", "") or item.get("category", ""))
            if cat:
                ai_rows.append({"category": cat, "platform": "tiktok"})
        if ai_rows:
            schema_ai = StructType(
                [StructField("category", StringType(), True), StructField("platform", StringType(), True)])
            df_ai = spark.createDataFrame(ai_rows, schema=schema_ai)
            _merge_or_create(spark, df_ai, "tiktok_ads_interests", "t.category = s.category")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
