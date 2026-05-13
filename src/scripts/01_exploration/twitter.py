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
import re  # noqa: E402
from datetime import datetime  # noqa: E402

TW_ROOT = os.path.join(PROCESSED_DATA, "X", "data")


def load_twitter_js(path: str):
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    clean = re.sub(r"^window\.YTD\.\w+\.\w+\s*=\s*", "", content.strip())
    return json.loads(clean)


def parse_twitter_date(date_str: str):
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.timestamp() * 1000
    except Exception:
        return None


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


def main():
    spark = build_spark_session("MyDigitalTwin - Twitter", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        # ── 1. Tweets ────────────────────────────────────────────────────────
        tweets_path = os.path.join(TW_ROOT, "tweets.js")
        if os.path.exists(tweets_path):
            raw_tweets = load_twitter_js(tweets_path)
            tweet_rows = []
            for entry in raw_tweets:
                t = entry.get("tweet", entry)
                text = t.get("full_text", t.get("text", ""))
                ts = t.get("created_at", "")
                tweet_id = t.get("id_str", "")
                lang = t.get("lang", "")
                rt_count = int(t.get("retweet_count", 0) or 0)
                fav_count = int(t.get("favorite_count", 0) or 0)
                is_rt = text.startswith("RT @")
                is_reply = bool(t.get("in_reply_to_status_id_str"))
                clean_text = re.sub(r"^(@\w+\s*)+", "", text).strip()
                urls = [u.get("expanded_url", "") for u in t.get("entities", {}).get("urls", [])]
                hashtags = [h.get("text", "").lower() for h in t.get("entities", {}).get("hashtags", [])]
                mentions = [m.get("screen_name", "") for m in t.get("entities", {}).get("user_mentions", [])]
                ts_ms = parse_twitter_date(ts)
                tweet_rows.append({
                    "tweet_id": tweet_id,
                    "text": clean_text,
                    "raw_text": text,
                    "lang": lang,
                    "created_at": ts,
                    "retweet_count": rt_count,
                    "favorite_count": fav_count,
                    "is_retweet": is_rt,
                    "is_reply": is_reply,
                    "has_media": bool(t.get("entities", {}).get("media")),
                    "hashtags": " ".join(hashtags),
                    "mentions": " ".join(mentions),
                    "urls": " ".join(urls),
                    "char_count": len(clean_text),
                    "word_count": len(clean_text.split()),
                    "timestamp_ms": int(ts_ms) if ts_ms else 0,
                })
            schema_tweets = StructType([
                StructField("tweet_id", StringType(), True),
                StructField("text", StringType(), True),
                StructField("raw_text", StringType(), True),
                StructField("lang", StringType(), True),
                StructField("created_at", StringType(), True),
                StructField("retweet_count", IntegerType(), True),
                StructField("favorite_count", IntegerType(), True),
                StructField("is_retweet", BooleanType(), True),
                StructField("is_reply", BooleanType(), True),
                StructField("has_media", BooleanType(), True),
                StructField("hashtags", StringType(), True),
                StructField("mentions", StringType(), True),
                StructField("urls", StringType(), True),
                StructField("char_count", IntegerType(), True),
                StructField("word_count", IntegerType(), True),
                StructField("timestamp_ms", LongType(), True),
            ])
            df_tweets = spark.createDataFrame(tweet_rows, schema=schema_tweets)
            df_tweets = df_tweets \
                .withColumn("event_date", F.to_timestamp(F.col("timestamp_ms") / 1000)) \
                .withColumn("event_year", F.year("event_date")) \
                .withColumn("event_month", F.date_format("event_date", "yyyy-MM")) \
                .withColumn("event_hour", F.hour("event_date")) \
                .withColumn("event_weekday", F.dayofweek("event_date")) \
                .withColumn("platform", F.lit("twitter"))
            _merge_or_create(spark, df_tweets, "twitter_tweets", "t.tweet_id = s.tweet_id")
        else:
            print("  ⚠ tweets.js introuvable — skip tweets")

        # ── 2. Likes ─────────────────────────────────────────────────────────
        likes_path = os.path.join(TW_ROOT, "like.js")
        if os.path.exists(likes_path):
            raw_likes = load_twitter_js(likes_path)
            like_rows = []
            for entry in raw_likes:
                lk = entry.get("like", entry)
                like_rows.append({
                    "tweet_id": lk.get("tweetId", ""),
                    "full_text": lk.get("fullText", ""),
                    "post_url": lk.get("expandedUrl", ""),
                })
            schema_likes = StructType([
                StructField("tweet_id", StringType(), True),
                StructField("full_text", StringType(), True),
                StructField("post_url", StringType(), True),
            ])
            df_likes = spark.createDataFrame(like_rows, schema=schema_likes) \
                .withColumn("platform", F.lit("twitter")) \
                .withColumn("action_type", F.lit("like")) \
                .withColumn("char_count", F.length("full_text")) \
                .withColumn("word_count", F.size(F.split(F.trim("full_text"), r"\s+")))
            _merge_or_create(spark, df_likes, "twitter_likes", "t.tweet_id = s.tweet_id")
        else:
            print("  ⚠ like.js introuvable — skip likes")

        # ── 3. Recherches sauvegardées ────────────────────────────────────────
        saved_path = os.path.join(TW_ROOT, "saved-search.js")
        if os.path.exists(saved_path):
            raw_ss = load_twitter_js(saved_path)
            saved_rows = []
            for item in raw_ss:
                if isinstance(item, dict):
                    query = (item.get("savedSearch", {}) or {}).get("query", "") or item.get("query", "")
                else:
                    query = str(item)
                if query:
                    saved_rows.append({"query": query, "platform": "twitter"})
            if saved_rows:
                schema_ss = StructType([
                    StructField("query", StringType(), True),
                    StructField("platform", StringType(), True),
                ])
                df_ss = spark.createDataFrame(saved_rows, schema=schema_ss)
                _merge_or_create(spark, df_ss, "twitter_saved_searches", "t.query = s.query")
        else:
            print("  ⚠ saved-search.js introuvable — skip")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
