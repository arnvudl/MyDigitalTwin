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
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType  # noqa: E402
from pyspark.ml.clustering import KMeans  # noqa: E402
from pyspark.ml.feature import VectorAssembler, StandardScaler  # noqa: E402
from delta.tables import DeltaTable  # noqa: E402

try:
    from config import K_BEHAVIORAL
except ImportError:
    K_BEHAVIORAL = 5

BEH_LABELS = {
    0: "Social & Messaging",
    1: "Entertainment Consumption",
    2: "Music & Audio",
    3: "Search & Discovery",
    4: "Video & Streaming",
}


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


def build_platform_profiles(spark):
    """Build one row per platform with aggregate behavioral features."""
    platform_aggs = []

    ig_comments = _safe_read(spark, "instagram_comments")
    if ig_comments is not None:
        agg = ig_comments.groupBy("platform").agg(
            F.count("*").alias("event_count"),
            F.avg("char_count").alias("avg_char_count"),
            F.countDistinct(F.date_format("event_date", "yyyy-MM")).alias("active_months"),
        )
        platform_aggs.append(agg)

    ig_likes = _safe_read(spark, "instagram_likes")
    if ig_likes is not None:
        agg = ig_likes.groupBy("platform").agg(
            F.count("*").alias("event_count"),
            F.lit(0.0).alias("avg_char_count"),
            F.countDistinct(F.date_format("event_date", "yyyy-MM")).alias("active_months"),
        )
        platform_aggs.append(agg)

    spotify = _safe_read(spark, "spotify_streams")
    if spotify is not None:
        agg = spotify.groupBy("data_platform").agg(
            F.count("*").alias("event_count"),
            F.avg("ms_played").alias("avg_char_count"),
            F.countDistinct(F.date_format("event_date", "yyyy-MM")).alias("active_months"),
        ).withColumnRenamed("data_platform", "platform")
        platform_aggs.append(agg)

    yt = _safe_read(spark, "youtube_watch")
    if yt is not None:
        agg = yt.groupBy("platform").agg(
            F.count("*").alias("event_count"),
            F.lit(0.0).alias("avg_char_count"),
            F.countDistinct(F.date_format("event_date", "yyyy-MM")).alias("active_months"),
        )
        platform_aggs.append(agg)

    tiktok = _safe_read(spark, "tiktok_watch")
    if tiktok is not None:
        agg = tiktok.groupBy("platform").agg(
            F.count("*").alias("event_count"),
            F.lit(0.0).alias("avg_char_count"),
            F.lit(1).alias("active_months"),
        )
        platform_aggs.append(agg)

    twitter = _safe_read(spark, "twitter_tweets")
    if twitter is not None:
        agg = twitter.groupBy("platform").agg(
            F.count("*").alias("event_count"),
            F.avg("char_count").alias("avg_char_count"),
            F.countDistinct(F.date_format("event_date", "yyyy-MM")).alias("active_months"),
        )
        platform_aggs.append(agg)

    if not platform_aggs:
        return None

    profiles = platform_aggs[0]
    for other in platform_aggs[1:]:
        profiles = profiles.unionByName(other, allowMissingColumns=True)

    profiles = profiles.fillna(0.0)
    return profiles


def main():
    spark = build_spark_session(
        "MyDigitalTwin-BehavioralClustering",
        driver_memory="4g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        profiles = build_platform_profiles(spark)
        if profiles is None:
            print("  ⚠ No platform data available — skip clustering")
            return

        feature_cols = ["event_count", "avg_char_count", "active_months"]
        assembler = VectorAssembler(inputCols=feature_cols, outputCol="_features_raw")
        profiles = assembler.transform(profiles)

        scaler = StandardScaler(inputCol="_features_raw", outputCol="features",
                                withStd=True, withMean=True)
        scaler_model = scaler.fit(profiles)
        profiles = scaler_model.transform(profiles)

        k = min(K_BEHAVIORAL, profiles.count())
        kmeans = KMeans(k=k, seed=42, featuresCol="features", predictionCol="cluster_id")
        model = kmeans.fit(profiles)
        result = model.transform(profiles)

        result = result.withColumn(
            "cluster_label",
            F.udf(lambda cid: BEH_LABELS.get(cid, f"Cluster {cid}"), StringType())(F.col("cluster_id"))
        ).select("platform", "event_count", "avg_char_count", "active_months", "cluster_id", "cluster_label")

        # Computed table → delete + append
        table_path = os.path.join(WAREHOUSE, "behavioral_clusters")
        if DeltaTable.isDeltaTable(spark, table_path):
            DeltaTable.forPath(spark, table_path).delete()
            result.write.format("delta").mode("append").save(table_path)
        else:
            result.write.format("delta").mode("overwrite").save(table_path)

        count = spark.read.format("delta").load(table_path).count()
        print(f"  ✓ behavioral_clusters — {count:,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
