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
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    StructType, StructField, StringType, IntegerType,
    ArrayType, LongType, DoubleType,
)
from pyspark.ml.feature import Tokenizer, StopWordsRemover, NGram  # noqa: E402
from delta.tables import DeltaTable  # noqa: E402


STOPWORDS_EXTRA = [
    "les","des","une","sur","avec","dans","qui","que","par","plus",
    "tout","bien","comme","mais","mon","ton","son","nos","mes",
    "faire","comment","aussi","encore","très",
    "the","and","for","with","you","your","this","that","from",
    "are","was","not","its","but","all","new","best","how",
    "https","http","www","com","org","net","html","utm","amp",
    "watch","video","clip","official","officiel","youtube","shorts",
    "16x9","inh","vid","1920x1080","15s","officiel)","(clip",
    "(official","video)","(ft","music","choisissez","chrome",
    "google","gmail","recherche","online","redirect","editor",
    "lil","trio","los","del","les","von",
]

NOISE_RE = (
    r'(?i)'
    r'\b\d{1,4}x\d{1,4}\b|\bINH\b'
    r'|Choisissez Chrome|Kies Chrome|Choose Chrome'
    r'|^Redirect(?:ion)?[\.\s…]*$|Ad Blocker|VID\s+\d'
    r'|_[A-Z]{2}\b|\bBoost_\d|LinkedAccounts|FreeBankAccount'
    r'|\b\d+\s*sec\b|casino|^Shortened[:\s]'
    r'|[一-鿿぀-ヿ]'
    r'|\blening\b|\bkrediet\b|CI/CD|TeamCity|JetBrains'
    r'|On the jobsite|leaders aren|\bvolvo\b|\bDEWALT\b'
    r'|reconditionné.*Back\s*Mark|Enjoy a better|^Loading[.\s]*$'
    r'|lust\s+god|Recherche\s+Google|(\w+)\s+\1\.(com|net|org|be|fr|io)'
)

PLATFORM_SOURCE = {
    "youtube":           ("youtube_watch",      "title"),
    "google":            ("google_searches",    "query"),
    "chrome":            ("google_chrome",      "title"),
    "spotify":           ("spotify_streams",    "artistName"),
    "netflix":           ("netflix_views",      "show_title"),
    "tiktok":            ("tiktok_searches",    "query"),
    "tiktok_likes":      ("tiktok_searches",    "query"),
    "tiktok_search":     ("tiktok_searches",    "query"),
    "instagram":         ("instagram_searches", "query"),
    "instagram_saved":   ("instagram_searches", "query"),
    "ig_search":         ("instagram_searches", "query"),
    "ig_posts":          ("instagram_searches", "query"),
    "ig_videos":         ("instagram_searches", "query"),
    "ig_stories":        ("instagram_searches", "query"),
    "instagram_comment": ("instagram_searches", "query"),
    "twitter":           ("twitter_tweets",     "full_text"),
}


def main():
    spark = build_spark_session(
        "MyDigitalTwin-FusionViz",
        driver_memory="4g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        def read_table(name):
            return spark.read.format("delta").load(os.path.join(WAREHOUSE, name))

        beh_clusters = read_table("behavioral_clusters")
        print("Profils comportementaux :")
        beh_clusters.show(truncate=60)

        beh_info = {row["cluster_id"]: row.asDict() for row in beh_clusters.collect()}
        print(f"\n{len(beh_info)} clusters chargés.")

        stop_all = (StopWordsRemover.loadDefaultStopWords("english")
                  + StopWordsRemover.loadDefaultStopWords("french")
                  + STOPWORDS_EXTRA)

        def extract_top_words(df, text_col, n=15):
            clean = (
                df.filter(F.col(text_col).isNotNull() & (F.length(F.col(text_col)) > 2))
                .withColumnRenamed(text_col, "_text")
                .filter(~F.col("_text").rlike(r'@|^https?://|%[0-9a-fA-F]{2}'))
            )
            tok = Tokenizer(inputCol="_text", outputCol="_words").transform(clean)
            flt = StopWordsRemover(inputCol="_words", outputCol="_tokens",
                                   stopWords=stop_all).transform(tok)
            return (flt.select(F.explode("_tokens").alias("w"))
                       .filter(F.length("w") > 2)
                       .filter(~F.col("w").rlike(r'^\d'))
                       .filter(~F.col("w").rlike(r'[@%#\(\)]'))
                       .groupBy("w").count()
                       .orderBy(F.desc("count")).limit(n)
                       .select("w").rdd.flatMap(lambda x: x).collect())

        def extract_bigrams(df, text_col, n=5):
            clean = (
                df.filter(F.col(text_col).isNotNull() & (F.length(F.col(text_col)) > 2))
                .withColumnRenamed(text_col, "_text")
                .filter(~F.col("_text").rlike(r'@|^https?://|%[0-9a-fA-F]{2}'))
            )
            tok = Tokenizer(inputCol="_text", outputCol="_words").transform(clean)
            flt = StopWordsRemover(inputCol="_words", outputCol="_tokens",
                                   stopWords=stop_all).transform(tok)
            bg = NGram(n=2, inputCol="_tokens", outputCol="_ng").transform(flt)
            return (bg.select(F.explode("_ng").alias("b"))
                      .filter(F.length("b") > 5)
                      .filter(~F.col("b").rlike(r'[@%#\(\)\d]'))
                      .groupBy("b").count()
                      .orderBy(F.desc("count")).limit(n)
                      .select("b").rdd.flatMap(lambda x: x).collect())

        def extract_samples(df, text_col, n=30):
            return (
                df.filter(F.col(text_col).isNotNull() & (F.length(F.col(text_col)) > 1))
                .filter(~F.col(text_col).rlike(r'@|^https?://|%[0-9a-fA-F]{2}'))
                .filter(~F.col(text_col).rlike(NOISE_RE))
                .filter(~F.col(text_col).rlike(r'^\s*[A-Z0-9_]{5,}\s'))
                .groupBy(text_col).count()
                .orderBy(F.desc("count")).limit(n)
                .select(text_col).rdd.flatMap(lambda x: x).collect()
            )

        def merge_kw(*lists):
            seen, result = set(), []
            for lst in lists:
                for w in lst:
                    if w not in seen:
                        seen.add(w); result.append(w)
            return result

        _df_cache = {}

        def get_df(table_name):
            if table_name not in _df_cache:
                try:
                    _df_cache[table_name] = read_table(table_name).cache()
                except Exception:
                    _df_cache[table_name] = None
            return _df_cache[table_name]

        # ── C2. Dynamic keyword extraction per cluster ─────────────────────────
        cluster_keywords = {}
        cluster_samples = {}

        for cid, info in sorted(beh_info.items()):
            platforms = list(info.get("top_platforms") or [])
            seen_tables, kw_parts, sample_parts = set(), [], []

            for p in platforms:
                mapping = PLATFORM_SOURCE.get(p)
                if not mapping:
                    continue
                table_name, text_col = mapping
                if table_name in seen_tables:
                    continue
                df = get_df(table_name)
                if df is None:
                    continue
                seen_tables.add(table_name)
                kw_parts.append(extract_bigrams(df, text_col, n=4))
                kw_parts.append(extract_top_words(df, text_col, n=12))
                sample_parts.append(extract_samples(df, text_col, n=20))
                if len(seen_tables) >= 3:
                    break

            cluster_keywords[cid] = merge_kw(*kw_parts)

            all_s, seen_s = [], set()
            for lst in sample_parts:
                for s in lst:
                    if s not in seen_s:
                        seen_s.add(s); all_s.append(s)
            cluster_samples[cid] = all_s[:30]

            label = info["label"]
            print(f"  [{cid}] {label}")
            print(f"       sources : {sorted(seen_tables)}")
            print(f"       keywords: {cluster_keywords[cid][:8]}")
            print()

        # ── C3. Write interest_profiles ───────────────────────────────────────
        schema_ip = StructType([
            StructField("cluster_id",    IntegerType(), False),
            StructField("label",         StringType(),  False),
            StructField("emoji",         StringType(),  True),
            StructField("keywords",      ArrayType(StringType()), True),
            StructField("top_platforms", ArrayType(StringType()), True),
            StructField("avg_hour",      DoubleType(),  True),
            StructField("time_period",   StringType(),  True),
            StructField("day_type",      StringType(),  True),
            StructField("item_count",    LongType(),    True),
            StructField("sample_items",  ArrayType(StringType()), True),
        ])

        interest_rows = [
            (
                cid,
                info["label"],
                info["emoji"],
                cluster_keywords.get(cid, []),
                list(info.get("top_platforms") or []),
                float(info["avg_hour"]),
                info["time_period"],
                info["day_type"],
                info["item_count"],
                cluster_samples.get(cid, []),
            )
            for cid, info in sorted(beh_info.items())
        ]

        interest_profiles_df = spark.createDataFrame(interest_rows, schema_ip)
        out_path = os.path.join(WAREHOUSE, "interest_profiles")

        if DeltaTable.isDeltaTable(spark, out_path):
            (
                DeltaTable.forPath(spark, out_path).alias("target")
                .merge(interest_profiles_df.alias("source"), "target.cluster_id = source.cluster_id")
                .whenMatchedUpdateAll()
                .whenNotMatchedInsertAll()
                .execute()
            )
        else:
            interest_profiles_df.write.format("delta").mode("overwrite").save(out_path)

        count = spark.read.format("delta").load(out_path).count()
        print(f"  ✓ interest_profiles — {count:,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
