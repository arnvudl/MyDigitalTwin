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
from pyspark.ml.feature import Tokenizer, StopWordsRemover, NGram  # noqa: E402

try:
    from config import CATEGORY_KEYWORDS
except ImportError:
    CATEGORY_KEYWORDS = {}


def _safe_read(spark, table_name: str):
    path = os.path.join(WAREHOUSE, table_name)
    if not os.path.isdir(path):
        print(f"  ⚠ {table_name} introuvable — skip")
        return None
    try:
        return spark.read.format("delta").load(path)
    except Exception as e:
        print(f"  ⚠ {table_name} lecture échouée: {e} — skip")
        return None


def _analyze_text_source(spark, df, text_col: str, source_name: str):
    if df is None:
        return
    df = df.filter(F.col(text_col).isNotNull() & (F.length(F.col(text_col)) > 0))
    if df.rdd.isEmpty():
        return

    tokenizer = Tokenizer(inputCol=text_col, outputCol="_tokens_raw")
    df = tokenizer.transform(df)

    remover = StopWordsRemover(inputCol="_tokens_raw", outputCol="_tokens",
                               locale="fr", caseSensitive=False)
    df = remover.transform(df)

    # Unigrams
    freq = (
        df.select(F.explode("_tokens").alias("word"))
          .filter(F.length("word") > 2)
          .groupBy("word")
          .count()
          .orderBy(F.desc("count"))
    )
    print(f"\n  [{source_name}] Top unigrams:")
    for row in freq.limit(10).collect():
        print(f"    {row['word']}: {row['count']}")

    # Bigrams
    ngram = NGram(n=2, inputCol="_tokens", outputCol="_bigrams")
    df_bi = ngram.transform(df)
    bigram_freq = (
        df_bi.select(F.explode("_bigrams").alias("bigram"))
             .groupBy("bigram")
             .count()
             .orderBy(F.desc("count"))
    )
    print(f"  [{source_name}] Top bigrams:")
    for row in bigram_freq.limit(5).collect():
        print(f"    {row['bigram']}: {row['count']}")

    # Category gap analysis
    if CATEGORY_KEYWORDS:
        all_words = set(r["word"] for r in freq.collect())
        for cat, keywords in CATEGORY_KEYWORDS.items():
            matched = [k for k in keywords if k.lower() in all_words]
            if not matched:
                print(f"  [{source_name}] Gap: category '{cat}' has no matching terms")


def main():
    spark = build_spark_session(
        "MyDigitalTwin-FrequencyAnalysis",
        driver_memory="4g",
        shuffle_partitions=8,
        delta=True,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        sources = [
            ("instagram_comments", "text", "Instagram Comments"),
            ("instagram_searches", "search_text", "Instagram Searches"),
            ("google_searches", "query", "Google Searches"),
            ("youtube_watch", "title", "YouTube Watch"),
            ("youtube_searches", "title", "YouTube Searches"),
            ("spotify_streams", "trackName", "Spotify Tracks"),
            ("tiktok_searches", "query", "TikTok Searches"),
            ("twitter_tweets", "text", "Twitter Tweets"),
        ]

        for table_name, text_col, source_name in sources:
            df = _safe_read(spark, table_name)
            _analyze_text_source(spark, df, text_col, source_name)

        print("\n  ✓ Content frequency analysis complete — no Delta output (analysis only)")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
