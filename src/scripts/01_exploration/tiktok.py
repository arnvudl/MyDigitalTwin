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


TIKTOK_DIR = os.path.join(PROCESSED_DATA, "TIKTOK")
MY_USERNAME = "arnvudl"


def _load_tiktok_data() -> dict:
    path = os.path.join(TIKTOK_DIR, "user_data_tiktok.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"TikTok data not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_dt(ts_str: str) -> int:
    """Parse TikTok UTC timestamp string to unix seconds."""
    from datetime import datetime, timezone
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        return 0


def extract_video_id(url: str) -> str:
    m = re.search(r"/video/(\d+)", url or "")
    return m.group(1) if m else ""


def anonymize(username: str) -> str:
    return "me" if username == MY_USERNAME else "other"


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
    spark = build_spark_session("MyDigitalTwin - TikTok", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        data = _load_tiktok_data()
        activity = data.get("Activity", {})

        # Watch history
        watch_list = activity.get("Video Browsing History", {}).get("VideoList", [])
        watch_rows = [
            {
                "video_id": extract_video_id(e.get("VideoLink", "")),
                "timestamp": parse_dt(e.get("Date", "")),
                "platform": "tiktok",
            }
            for e in watch_list
        ]
        if watch_rows:
            df = spark.createDataFrame(watch_rows, schema=StructType([
                StructField("video_id", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ]))
            _merge_table(spark, df, "tiktok_watch", "t.video_id = s.video_id AND t.timestamp = s.timestamp")

        # Likes
        like_list = activity.get("Like List", {}).get("ItemFavoriteList", [])
        like_rows = [
            {
                "video_id": extract_video_id(e.get("Link", "")),
                "timestamp": parse_dt(e.get("Date", "")),
                "platform": "tiktok",
            }
            for e in like_list
        ]
        if like_rows:
            df = spark.createDataFrame(like_rows, schema=StructType([
                StructField("video_id", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ]))
            _merge_table(spark, df, "tiktok_likes", "t.video_id = s.video_id AND t.timestamp = s.timestamp")

        # Saves / favorites
        save_list = activity.get("Favorite Videos", {}).get("FavoriteVideoList", [])
        save_rows = [
            {
                "video_id": extract_video_id(e.get("Link", "")),
                "timestamp": parse_dt(e.get("Date", "")),
                "platform": "tiktok",
            }
            for e in save_list
        ]
        if save_rows:
            df = spark.createDataFrame(save_rows, schema=StructType([
                StructField("video_id", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ]))
            _merge_table(spark, df, "tiktok_saves", "t.video_id = s.video_id AND t.timestamp = s.timestamp")

        # Search history
        search_list = activity.get("Search History", {}).get("SearchList", [])
        search_rows = [
            {
                "query": e.get("SearchTerm", ""),
                "timestamp": parse_dt(e.get("Date", "")),
                "platform": "tiktok",
            }
            for e in search_list
        ]
        if search_rows:
            df = spark.createDataFrame(search_rows, schema=StructType([
                StructField("query", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ]))
            _merge_table(spark, df, "tiktok_searches", "t.query = s.query AND t.timestamp = s.timestamp")

        # Comments
        comment_list = activity.get("Comment", {}).get("CommentsList", [])
        comment_rows = [
            {
                "text": e.get("Comment", ""),
                "timestamp": parse_dt(e.get("Date", "")),
                "platform": "tiktok",
            }
            for e in comment_list
        ]
        if comment_rows:
            df = spark.createDataFrame(comment_rows, schema=StructType([
                StructField("text", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ]))
            _merge_table(spark, df, "tiktok_comments", "t.text = s.text AND t.timestamp = s.timestamp")

        # Direct messages metadata
        dm_data = data.get("Direct Messages", {}).get("ChatHistory", {})
        dm_rows = []
        for conv_key, messages in dm_data.items():
            for msg in messages:
                sender = msg.get("From", "")
                dm_rows.append({
                    "conv_id": conv_key,
                    "sender_anon": anonymize(sender),
                    "timestamp": parse_dt(msg.get("Date", "")),
                    "msg_type": "text",
                    "platform": "tiktok",
                })
        if dm_rows:
            df = spark.createDataFrame(dm_rows, schema=StructType([
                StructField("conv_id", StringType()),
                StructField("sender_anon", StringType()),
                StructField("timestamp", LongType()),
                StructField("msg_type", StringType()),
                StructField("platform", StringType()),
            ]))
            _merge_table(spark, df, "tiktok_messages_meta",
                         "t.conv_id = s.conv_id AND t.sender_anon = s.sender_anon AND t.timestamp = s.timestamp")

        # Favorite hashtags (optional)
        hashtag_list = activity.get("Hashtag", {}).get("HashtagList", [])
        if hashtag_list:
            hashtag_rows = [{"hashtag": e.get("HashtagName", ""), "link": e.get("HashtagLink", "")} for e in hashtag_list]
            df = spark.createDataFrame(hashtag_rows, schema=StructType([
                StructField("hashtag", StringType()),
                StructField("link", StringType()),
            ]))
            _merge_table(spark, df, "tiktok_favorite_hashtags", "t.hashtag = s.hashtag")

        # Ads interests (optional)
        ads_list = activity.get("Ads and data", {}).get("AdsInterests", [])
        if ads_list:
            ads_rows = [{"interest": e} if isinstance(e, str) else {"interest": e.get("name", "")} for e in ads_list]
            df = spark.createDataFrame(ads_rows, schema=StructType([StructField("interest", StringType())]))
            _merge_table(spark, df, "tiktok_ads_interests", "t.interest = s.interest")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
