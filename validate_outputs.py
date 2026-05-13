"""Smoke-test all analytical output tables.

Checks schema (required columns present) and row counts for every table
produced by the converted scripts.

Exit code 0 if all pass, 1 if any fail.

Usage:
    python validate_outputs.py
"""

import sys
import os

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

from config import build_spark_session, WAREHOUSE  # noqa: E402

EXPECTATIONS = {
    "instagram_comments":       {"min_rows": 1, "required_columns": ["text", "timestamp", "platform"]},
    "instagram_likes":          {"min_rows": 1, "required_columns": ["timestamp", "post_url", "platform"]},
    "instagram_messages_meta":  {"min_rows": 1, "required_columns": ["conv_id", "timestamp_ms", "msg_type"]},
    "instagram_saved":          {"min_rows": 1, "required_columns": ["post_href", "timestamp"]},
    "instagram_posts_viewed":   {"min_rows": 0, "required_columns": ["timestamp"]},
    "instagram_videos_watched": {"min_rows": 0, "required_columns": ["timestamp"]},
    "instagram_story_likes":    {"min_rows": 0, "required_columns": ["timestamp"]},
    "instagram_searches":       {"min_rows": 1, "required_columns": ["query", "timestamp"]},
    "google_searches":          {"min_rows": 1, "required_columns": ["query", "timestamp", "platform"]},
    "google_chrome":            {"min_rows": 1, "required_columns": ["url", "timestamp", "platform"]},
    "youtube_watch":            {"min_rows": 1, "required_columns": ["title", "timestamp", "platform"]},
    "youtube_searches":         {"min_rows": 1, "required_columns": ["query", "timestamp", "platform"]},
    "spotify_streams":          {"min_rows": 1, "required_columns": ["track_name", "artist_name", "ms_played"]},
    "spotify_liked_songs":      {"min_rows": 1, "required_columns": ["track_name", "artist_name"]},
    "spotify_playlists":        {"min_rows": 1, "required_columns": ["playlist_name", "track_name"]},
    "spotify_searches":         {"min_rows": 0, "required_columns": ["query"]},
    "tiktok_watch":             {"min_rows": 1, "required_columns": ["video_id", "timestamp"]},
    "tiktok_likes":             {"min_rows": 1, "required_columns": ["video_id", "timestamp"]},
    "tiktok_saves":             {"min_rows": 0, "required_columns": ["video_id", "timestamp"]},
    "tiktok_searches":          {"min_rows": 1, "required_columns": ["query", "timestamp"]},
    "tiktok_comments":          {"min_rows": 0, "required_columns": ["text", "timestamp"]},
    "tiktok_messages_meta":     {"min_rows": 0, "required_columns": ["conv_id", "timestamp"]},
    "twitter_tweets":           {"min_rows": 1, "required_columns": ["text", "timestamp"]},
    "twitter_likes":            {"min_rows": 1, "required_columns": ["tweet_id", "timestamp"]},
    "netflix_views":            {"min_rows": 1, "required_columns": ["title", "event_date", "platform"]},
    "behavioral_clusters":      {"min_rows": 1, "required_columns": ["cluster_id"]},
    "interest_profiles":        {"min_rows": 1, "required_columns": ["cluster_id"]},
}


def main() -> None:
    spark = build_spark_session("MyDigitalTwin-Validate", driver_memory="1g", shuffle_partitions=2)
    spark.sparkContext.setLogLevel("ERROR")

    passed = 0
    failed = 0

    try:
        for table_name, exp in EXPECTATIONS.items():
            table_path = os.path.join(WAREHOUSE, table_name)
            min_rows = exp["min_rows"]
            required_cols = exp["required_columns"]

            if not os.path.isdir(table_path):
                print(f"  ✗ {table_name} — MISSING (no directory at {table_path})")
                failed += 1
                continue

            try:
                df = spark.read.format("delta").load(table_path)
            except Exception as e:
                print(f"  ✗ {table_name} — READ ERROR: {e}")
                failed += 1
                continue

            actual_cols = set(df.columns)
            missing_cols = [c for c in required_cols if c not in actual_cols]
            if missing_cols:
                print(f"  ✗ {table_name} — SCHEMA MISMATCH: missing columns {missing_cols}")
                failed += 1
                continue

            row_count = df.count()
            if min_rows > 0 and row_count < min_rows:
                print(f"  ✗ {table_name} — {row_count} rows (expected >= {min_rows})")
                failed += 1
                continue

            print(f"  ✓ {table_name} — schema OK, {row_count:,} rows")
            passed += 1

    finally:
        spark.stop()

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
