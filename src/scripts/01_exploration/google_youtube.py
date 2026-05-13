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
from delta.tables import DeltaTable  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


GOOGLE_ROOT = os.path.join(PROCESSED_DATA, "GOOGLE")

MOIS = {
    "janv": 1, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "août": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12
}


def parse_google_date(text: str) -> int:
    if not text:
        return 0
    m = re.search(
        r'(\d{1,2})\s+(\w+\.?)\s+(\d{4}),?\s+(\d{2}):(\d{2}):(\d{2})',
        text
    )
    if not m:
        return 0
    day, month_str, year, h, mi, s = m.groups()
    month_key = month_str.lower().rstrip('.')
    month_num = MOIS.get(month_key[:4], None)
    if not month_num:
        return 0
    try:
        dt = datetime(int(year), month_num, int(day), int(h), int(mi), int(s),
                      tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def parse_html_activity(html_path: str, activity_type: str) -> list:
    print(f"  Lecture : {os.path.basename(html_path)}...")
    with open(html_path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    soup = BeautifulSoup(content, "lxml")
    cells = soup.find_all("div", class_="outer-cell")
    print(f"  Cellules trouvées : {len(cells):,}")

    rows = []
    total_cells = len(cells)
    for idx, cell in enumerate(cells):
        if idx % 5000 == 0 and idx > 0:
            print(f"  ... {idx:,}/{total_cells:,} cellules traitées ({idx*100//total_cells}%)")
        content_div = cell.find("div", class_="content-cell")
        if not content_div:
            continue

        links = content_div.find_all("a")
        main_lnk = links[0] if links else None
        sec_lnk = links[1] if len(links) > 1 else None

        title = main_lnk.get_text(strip=True) if main_lnk else ""
        url = main_lnk.get("href", "")[:300] if main_lnk else ""
        author = sec_lnk.get_text(strip=True) if sec_lnk and \
            any(x in sec_lnk.get("href", "") for x in ["channel", "user", "@"]) else ""

        full_text = content_div.get_text(separator=" | ")
        ts_ms = parse_google_date(full_text)

        if not title and not ts_ms:
            continue

        rows.append({
            "title": title,
            "url": url,
            "author": author,
            "timestamp_ms": ts_ms,
            "activity_type": activity_type,
            "platform": "google",
        })

    print(f"  Lignes extraites : {len(rows):,}")
    return rows


def make_df(spark, rows: list):
    tmp_path = "/tmp/tmp_make_df.json"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    print(f"  Écriture fichier temp ({len(rows):,} lignes)...")
    with open(tmp_path, "w", encoding="utf-8") as f:
        for row in rows:
            print(json.dumps(row), file=f)
    print(f"  Fichier temp écrit : {tmp_path}")
    print(f"  Lecture Spark JSON...")
    df = spark.read.json([tmp_path])
    print(f"  DataFrame créé — ajout colonnes temporelles...")
    df = df \
        .withColumn("event_date",    F.to_timestamp(F.col("timestamp_ms") / 1000)) \
        .withColumn("event_year",    F.year("event_date")) \
        .withColumn("event_month",   F.date_format("event_date", "yyyy-MM")) \
        .withColumn("event_hour",    F.hour("event_date")) \
        .withColumn("event_weekday", F.dayofweek("event_date")) \
        .withColumn("char_count",    F.length("title")) \
        .withColumn("word_count",    F.size(F.split(F.trim("title"), r"\s+")))
    return df


def _merge_or_create(spark, df, table_name: str, condition: str):
    path = os.path.join(WAREHOUSE, table_name)
    print(f"  Écriture Delta {table_name}...")
    if DeltaTable.isDeltaTable(spark, path):
        DeltaTable.forPath(spark, path).alias("t").merge(
            df.alias("s"), condition
        ).whenNotMatchedInsertAll().execute()
    else:
        df.write.format("delta").save(path)
    count = spark.read.format("delta").load(path).count()
    print(f"  ✓ {table_name} — {count:,} lignes")


def main():
    spark = build_spark_session("MyDigitalTwin - Google", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")

    try:
        # ── 1. Google Searches ────────────────────────────────────────────────
        search_path = os.path.join(GOOGLE_ROOT, "Mon activité", "Recherche", "MonActivité.html")
        if os.path.exists(search_path):
            print("[1/4] Lecture Google Searches...")
            search_rows = parse_html_activity(search_path, "google_search")
            df_search = make_df(spark, search_rows)
            print("  Extraction query depuis URL...")
            df_search = df_search.withColumn(
                "query",
                F.regexp_extract(F.col("url"), r"[?&]q=([^&]+)", 1)
            ).withColumn(
                "query",
                F.regexp_replace(F.col("query"), r"\+", " ")
            )
            _merge_or_create(spark, df_search, "google_searches",
                "t.query = s.query AND t.timestamp_ms = s.timestamp_ms")
        else:
            print("  ⚠ MonActivité.html (Recherche) introuvable — skip")

        # ── 2. Chrome History ─────────────────────────────────────────────────
        chrome_path = os.path.join(GOOGLE_ROOT, "Mon activité", "Chrome", "MonActivité.html")
        if os.path.exists(chrome_path):
            print("[2/4] Lecture Chrome history...")
            chrome_rows = parse_html_activity(chrome_path, "chrome_visit")
            df_chrome = make_df(spark, chrome_rows)
            print("  Extraction domaine depuis URL...")
            df_chrome = df_chrome.withColumn(
                "domain",
                F.regexp_extract(F.col("url"), r"https?://(?:www\.)?([^/]+)", 1)
            )
            _merge_or_create(spark, df_chrome, "google_chrome",
                "t.url = s.url AND t.timestamp_ms = s.timestamp_ms")
        else:
            print("  ⚠ MonActivité.html (Chrome) introuvable — skip")

        # ── 3. YouTube Watch History ──────────────────────────────────────────
        yt_watch_path = os.path.join(
            GOOGLE_ROOT, "YouTube et YouTube Music", "historique", "watch-history.html"
        )
        if os.path.exists(yt_watch_path):
            print("[3/4] Lecture YouTube Watch history...")
            yt_watch_rows = parse_html_activity(yt_watch_path, "youtube_watch")
            df_yt_watch = make_df(spark, yt_watch_rows)
            print("  Extraction video_id + filtrage pubs...")
            df_yt_watch = df_yt_watch.withColumn(
                "video_id",
                F.regexp_extract(F.col("url"), r"[?&]v=([a-zA-Z0-9_-]{11})", 1)
            )
            df_yt_watch = df_yt_watch.filter(
                ~F.col("url").contains("googleadservices") &
                ~F.col("url").contains("doubleclick") &
                ~F.col("url").contains("googlevideo.com/videoplayback") &
                ~F.col("title").rlike(r"(?i)^(publicité|pub|advertisement|ad)$") &
                (F.col("video_id") != "")
            )
            _merge_or_create(spark, df_yt_watch, "youtube_watch",
                "t.video_id = s.video_id AND t.timestamp_ms = s.timestamp_ms")
        else:
            print("  ⚠ watch-history.html introuvable — skip")

        # ── 4. YouTube Search History ─────────────────────────────────────────
        yt_search_path = os.path.join(
            GOOGLE_ROOT, "YouTube et YouTube Music", "historique", "Historique des recherches.html"
        )
        if os.path.exists(yt_search_path):
            print("[4/4] Lecture YouTube Search history...")
            yt_search_rows = parse_html_activity(yt_search_path, "youtube_search")
            df_yt_search = make_df(spark, yt_search_rows)
            print("  Filtrage pubs YouTube Search...")
            df_yt_search = df_yt_search.filter(
                ~F.col("title").rlike(r"(?i)^Shortened:") &
                ~F.col("title").rlike(r"(?i)^(RAD|ROK|INH|AYF|ADS|ADV)[\s_]") &
                ~F.col("title").rlike(r"[0-9]{4}x[0-9]{3,4}") &
                ~F.col("title").rlike(r"_[0-9]+s$") &
                ~F.col("title").rlike(r"(?i)(partnership|campaign|creative)") &
                (F.length("title") > 2) &
                ~F.col("title").rlike(r"^[A-Z0-9_\s]{20,}$")
            )
            _merge_or_create(spark, df_yt_search, "youtube_searches",
                "t.title = s.title AND t.timestamp_ms = s.timestamp_ms")
        else:
            print("  ⚠ Historique des recherches.html introuvable — skip")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
