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
    StructType,
    StructField,
    StringType,
    LongType,
)
from delta.tables import DeltaTable  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
import json  # noqa: E402
import glob  # noqa: E402
import re  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

GOOGLE_DIR = os.path.join(PROCESSED_DATA, "GOOGLE")
YOUTUBE_DIR = os.path.join(GOOGLE_DIR, "YouTube et YouTube Music", "historique")

MOIS = {
    "janv.": "01", "févr.": "02", "mars": "03", "avr.": "04",
    "mai": "05", "juin": "06", "juil.": "07", "août": "08",
    "sept.": "09", "oct.": "10", "nov.": "11", "déc.": "12",
}

# YouTube ad channel patterns to filter out
AD_PATTERNS = re.compile(r"(pub\.|publicité|sponsored|annonce)", re.IGNORECASE)


def parse_google_date(date_str: str) -> int:
    """Parse French Google Takeout date to unix timestamp."""
    try:
        for fr, num in MOIS.items():
            date_str = date_str.replace(fr, num)
        # Format: "25 01 2023 à 14:30:00 UTC+1"
        date_str = re.sub(r"\s*UTC[+-]\d+", "", date_str).strip()
        date_str = date_str.replace(" à ", " ")
        dt = datetime.strptime(date_str, "%d %m %Y %H:%M:%S")
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        return 0


def parse_html_activity(path: str) -> list[dict]:
    """Parse a Google Takeout HTML activity file into a list of records."""
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    rows = []
    for cell in soup.find_all("div", class_="content-cell"):
        links = cell.find_all("a")
        if not links:
            continue
        url = links[0].get("href", "")
        title = links[0].get_text(strip=True)
        date_text = cell.get_text(separator=" ").strip()
        # Date is usually the last text segment after the links
        date_match = re.search(r"(\d{1,2}\s+\w+\.?\s+\d{4}\s+à\s+\d{2}:\d{2}:\d{2})", date_text)
        ts = parse_google_date(date_match.group(1)) if date_match else 0
        rows.append({"url": url, "title": title, "timestamp": ts})
    return rows


def make_df(spark, rows: list[dict], schema: StructType, tmp_path: str):
    """Write rows as NDJSON and read back with Spark (avoids large createDataFrame calls)."""
    with open(tmp_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    df = spark.read.schema(schema).json(tmp_path)
    return df


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
    spark = build_spark_session("MyDigitalTwin - Google", driver_memory="6g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    tmp_path = os.path.join(WAREHOUSE, "_tmp_make_df.json")
    try:
        # Google Search history (HTML files — French Takeout format)
        search_html_files = glob.glob(
            os.path.join(GOOGLE_DIR, "Mon activité", "Recherche", "*.html"), recursive=False
        )
        search_rows = []
        for path in search_html_files:
            rows = parse_html_activity(path)
            for r in rows:
                # Strip "A recherché" or "Recherché" prefix from title
                query = re.sub(r"^(A recherché\xa0?|Recherché\s*)", "", r.get("title", "")).strip()
                if query:
                    search_rows.append({"query": query, "timestamp": r.get("timestamp", 0), "platform": "google"})

        if search_rows:
            schema = StructType([
                StructField("query", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ])
            df = make_df(spark, search_rows, schema, tmp_path)
            df = df.withColumn("event_date", F.to_date(F.from_unixtime("timestamp")))
            _merge_table(spark, df, "google_searches", "t.query = s.query AND t.timestamp = s.timestamp")

        # Google Chrome browsing history (Historique.json — French Takeout format)
        chrome_rows = []
        chrome_json = os.path.join(GOOGLE_DIR, "Chrome", "Historique.json")
        if os.path.exists(chrome_json):
            with open(chrome_json, encoding="utf-8") as f:
                data = json.load(f)
            for e in data.get("Browser History", []):
                try:
                    ts = int(e.get("time_usec", 0)) // 1_000_000
                except Exception:
                    ts = 0
                chrome_rows.append({
                    "url": e.get("url", ""),
                    "title": e.get("title", ""),
                    "timestamp": ts,
                    "platform": "google",
                })
        else:
            # Fallback: HTML activity files
            html_files = glob.glob(os.path.join(GOOGLE_DIR, "Chrome", "*.html"))
            for path in html_files:
                rows = parse_html_activity(path)
                for r in rows:
                    r["platform"] = "google"
                chrome_rows.extend(rows)

        if chrome_rows:
            schema = StructType([
                StructField("url", StringType()),
                StructField("title", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ])
            df = make_df(spark, chrome_rows, schema, tmp_path)
            df = df.withColumn("event_date", F.to_date(F.from_unixtime("timestamp")))
            _merge_table(spark, df, "google_chrome", "t.url = s.url AND t.timestamp = s.timestamp")

        # YouTube watch history (watch-history.html — French Takeout format)
        yt_watch_html = os.path.join(YOUTUBE_DIR, "watch-history.html")
        yt_watch_rows = []
        if os.path.exists(yt_watch_html):
            for r in parse_html_activity(yt_watch_html):
                if AD_PATTERNS.search(r.get("title", "")):
                    continue
                yt_watch_rows.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "timestamp": r.get("timestamp", 0),
                    "platform": "youtube",
                })

        if yt_watch_rows:
            schema = StructType([
                StructField("title", StringType()),
                StructField("url", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ])
            df = make_df(spark, yt_watch_rows, schema, tmp_path)
            df = df.withColumn("event_date", F.to_date(F.from_unixtime("timestamp")))
            _merge_table(spark, df, "youtube_watch", "t.url = s.url AND t.timestamp = s.timestamp")

        # YouTube search history (Historique des recherches.html — French Takeout format)
        yt_search_html = os.path.join(YOUTUBE_DIR, "Historique des recherches.html")
        yt_search_rows = []
        if os.path.exists(yt_search_html):
            for r in parse_html_activity(yt_search_html):
                query = re.sub(r"^Recherché\s*", "", r.get("title", "")).strip()
                if query:
                    yt_search_rows.append({
                        "query": query,
                        "timestamp": r.get("timestamp", 0),
                        "platform": "youtube",
                    })

        if yt_search_rows:
            schema = StructType([
                StructField("query", StringType()),
                StructField("timestamp", LongType()),
                StructField("platform", StringType()),
            ])
            df = make_df(spark, yt_search_rows, schema, tmp_path)
            df = df.withColumn("event_date", F.to_date(F.from_unixtime("timestamp")))
            _merge_table(spark, df, "youtube_searches", "t.query = s.query AND t.timestamp = s.timestamp")

    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        spark.stop()


if __name__ == "__main__":
    main()
