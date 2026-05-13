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
import re  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


TWITTER_DIR = os.path.join(PROCESSED_DATA, "X", "data")


def load_twitter_js(path: str) -> list | dict:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # Strip "window.YTD.<variable> = " prefix
    content = re.sub(r"^window\.\w+\.\w+\s*=\s*", "", content.strip())
    return json.loads(content)


def parse_twitter_date(ts_str: str) -> int:
    try:
        dt = datetime.strptime(ts_str, "%a %b %d %H:%M:%S %z %Y")
        return int(dt.timestamp())
    except Exception:
        return 0


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


def parse_tweets(spark):
    path = os.path.join(TWITTER_DIR, "tweets.js")
    if not os.path.exists(path):
        print("  ⚠ tweets.js introuvable — skip tweets")
        return None
    raw = load_twitter_js(path)
    rows = []
    for entry in raw:
        tweet = entry.get("tweet", entry)
        rows.append({
            "tweet_id": tweet.get("id_str", ""),
            "text": tweet.get("full_text", tweet.get("text", "")),
            "timestamp": parse_twitter_date(tweet.get("created_at", "")),
            "retweet_count": int(tweet.get("retweet_count", 0) or 0),
            "favorite_count": int(tweet.get("favorite_count", 0) or 0),
            "platform": "twitter",
        })
    schema = StructType([
        StructField("tweet_id", StringType()),
        StructField("text", StringType()),
        StructField("timestamp", LongType()),
        StructField("retweet_count", IntegerType()),
        StructField("favorite_count", IntegerType()),
        StructField("platform", StringType()),
    ])
    df = spark.createDataFrame(rows, schema=schema)
    return df.withColumn("event_date", F.to_date(F.from_unixtime("timestamp")))


def parse_likes(spark):
    path = os.path.join(TWITTER_DIR, "like.js")
    if not os.path.exists(path):
        print("  ⚠ like.js introuvable — skip likes")
        return None
    raw = load_twitter_js(path)
    rows = []
    for entry in raw:
        like = entry.get("like", entry)
        rows.append({
            "tweet_id": like.get("tweetId", ""),
            "full_text": like.get("fullText", ""),
            "timestamp": 0,
            "platform": "twitter",
        })
    schema = StructType([
        StructField("tweet_id", StringType()),
        StructField("full_text", StringType()),
        StructField("timestamp", LongType()),
        StructField("platform", StringType()),
    ])
    return spark.createDataFrame(rows, schema=schema)


def parse_saved_searches(spark):
    path = os.path.join(TWITTER_DIR, "saved-search.js")
    if not os.path.exists(path):
        return None
    raw = load_twitter_js(path)
    rows = []
    for entry in raw:
        ss = entry.get("savedSearch", entry)
        rows.append({
            "query": ss.get("query", ""),
            "timestamp": parse_twitter_date(ss.get("savedAt", "")),
        })
    schema = StructType([
        StructField("query", StringType()),
        StructField("timestamp", LongType()),
    ])
    return spark.createDataFrame(rows, schema=schema)


def main():
    spark = build_spark_session("MyDigitalTwin - Twitter", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        df = parse_tweets(spark)
        if df is not None:
            _merge_table(spark, df, "twitter_tweets", "t.tweet_id = s.tweet_id")

        df = parse_likes(spark)
        if df is not None:
            _merge_table(spark, df, "twitter_likes", "t.tweet_id = s.tweet_id")

        df = parse_saved_searches(spark)
        if df is not None:
            _merge_table(spark, df, "twitter_saved_searches", "t.query = s.query AND t.timestamp = s.timestamp")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
