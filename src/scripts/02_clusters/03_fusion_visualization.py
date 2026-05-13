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
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, ArrayType  # noqa: E402
from pyspark.ml.feature import Tokenizer, StopWordsRemover, NGram  # noqa: E402
from delta.tables import DeltaTable  # noqa: E402


_DF_CACHE: dict = {}


def _safe_read(spark, table_name: str):
    if table_name in _DF_CACHE:
        return _DF_CACHE[table_name]
    path = os.path.join(WAREHOUSE, table_name)
    if not os.path.isdir(path):
        return None
    try:
        df = spark.read.format("delta").load(path)
        _DF_CACHE[table_name] = df
        return df
    except Exception:
        return None


def extract_top_words(spark, cluster_id: int, text_sources: list) -> list[str]:
    all_tokens = None
    for df, text_col in text_sources:
        if df is None:
            continue
        df_cluster = df.filter(F.col("cluster_id") == cluster_id) if "cluster_id" in df.columns else df
        tok = Tokenizer(inputCol=text_col, outputCol="_tok_raw").transform(
            df_cluster.filter(F.col(text_col).isNotNull())
        )
        rem = StopWordsRemover(inputCol="_tok_raw", outputCol="_tok", locale="fr").transform(tok)
        words = rem.select(F.explode("_tok").alias("word")).filter(F.length("word") > 2)
        all_tokens = words if all_tokens is None else all_tokens.union(words)

    if all_tokens is None:
        return []
    top = all_tokens.groupBy("word").count().orderBy(F.desc("count")).limit(20)
    return [r["word"] for r in top.collect()]


def extract_bigrams(spark, cluster_id: int, text_sources: list) -> list[str]:
    all_bigrams = None
    for df, text_col in text_sources:
        if df is None:
            continue
        df_cluster = df.filter(F.col("cluster_id") == cluster_id) if "cluster_id" in df.columns else df
        tok = Tokenizer(inputCol=text_col, outputCol="_tok_raw").transform(
            df_cluster.filter(F.col(text_col).isNotNull())
        )
        rem = StopWordsRemover(inputCol="_tok_raw", outputCol="_tok", locale="fr").transform(tok)
        ngram = NGram(n=2, inputCol="_tok", outputCol="_bigrams").transform(rem)
        bi = ngram.select(F.explode("_bigrams").alias("bigram"))
        all_bigrams = bi if all_bigrams is None else all_bigrams.union(bi)

    if all_bigrams is None:
        return []
    top = all_bigrams.groupBy("bigram").count().orderBy(F.desc("count")).limit(10)
    return [r["bigram"] for r in top.collect()]


def extract_samples(df, text_col: str, cluster_id: int, n: int = 5) -> list[str]:
    if df is None or text_col not in df.columns:
        return []
    rows = (
        df.filter(F.col("cluster_id") == cluster_id if "cluster_id" in df.columns else F.lit(True))
          .filter(F.col(text_col).isNotNull())
          .select(text_col)
          .limit(n)
          .collect()
    )
    return [r[text_col] for r in rows]


def main():
    spark = build_spark_session(
        "MyDigitalTwin-FusionViz",
        driver_memory="4g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        beh_clusters = _safe_read(spark, "behavioral_clusters")
        if beh_clusters is None:
            print("  ⚠ behavioral_clusters introuvable — run 02_behavioral_clustering.py first")
            return

        cluster_ids = [r["cluster_id"] for r in beh_clusters.select("cluster_id").distinct().collect()]

        text_sources = [
            (_safe_read(spark, "instagram_comments"), "text"),
            (_safe_read(spark, "twitter_tweets"), "text"),
            (_safe_read(spark, "google_searches"), "query"),
            (_safe_read(spark, "youtube_searches"), "query"),
            (_safe_read(spark, "tiktok_searches"), "query"),
            (_safe_read(spark, "spotify_streams"), "track_name"),
        ]

        profiles_rows = []
        for cluster_id in cluster_ids:
            cluster_info = beh_clusters.filter(F.col("cluster_id") == cluster_id).first()
            label = cluster_info["cluster_label"] if cluster_info else f"Cluster {cluster_id}"

            top_words = extract_top_words(spark, cluster_id, text_sources)
            bigrams = extract_bigrams(spark, cluster_id, text_sources)
            samples = extract_samples(
                _safe_read(spark, "instagram_comments"), "text", cluster_id
            )

            profiles_rows.append({
                "cluster_id": cluster_id,
                "cluster_label": label,
                "top_words": top_words,
                "top_bigrams": bigrams,
                "sample_texts": samples,
            })

        schema = StructType([
            StructField("cluster_id", IntegerType()),
            StructField("cluster_label", StringType()),
            StructField("top_words", ArrayType(StringType())),
            StructField("top_bigrams", ArrayType(StringType())),
            StructField("sample_texts", ArrayType(StringType())),
        ])
        result = spark.createDataFrame(profiles_rows, schema=schema)

        # Computed table → delete + append
        table_path = os.path.join(WAREHOUSE, "interest_profiles")
        if DeltaTable.isDeltaTable(spark, table_path):
            DeltaTable.forPath(spark, table_path).delete()
            result.write.format("delta").mode("append").save(table_path)
        else:
            result.write.format("delta").mode("overwrite").save(table_path)

        count = spark.read.format("delta").load(table_path).count()
        print(f"  ✓ interest_profiles — {count:,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
