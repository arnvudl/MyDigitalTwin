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
    StructType, StructField, StringType, IntegerType, FloatType,
    ArrayType, LongType, DoubleType,
)
from pyspark.ml.feature import VectorAssembler, StandardScaler  # noqa: E402
from pyspark.ml.clustering import KMeans  # noqa: E402
from pyspark.ml.evaluation import ClusteringEvaluator  # noqa: E402
from delta.tables import DeltaTable  # noqa: E402

try:
    from config import K_BEHAVIORAL
except ImportError:
    K_BEHAVIORAL = 4

BEH_LABELS = {
    0: {"label": "📱 Réseaux & Médias · Après-midi",  "emoji": "📱"},
    1: {"label": "🌐 Navigation Chrome · Après-midi", "emoji": "🌐"},
    2: {"label": "👻 Sauvegardes IG · Rare",          "emoji": "👻"},
    3: {"label": "🎬 Netflix · Soirée",               "emoji": "🎬"},
}


def safe_read(spark, name, hour_col="event_hour", weekday_col="event_weekday",
              platform_name=None, weight_val=None, limit=None):
    try:
        df = spark.read.format("delta").load(os.path.join(WAREHOUSE, name))
        w_col = F.col("interaction_weight").cast(FloatType()) if "interaction_weight" in df.columns \
                else F.lit(weight_val or 1.0).cast(FloatType())
        sel = df.select(
            F.col(hour_col).alias("hour"),
            F.col(weekday_col).alias("weekday"),
            F.lit(platform_name or name).alias("platform"),
            w_col.alias("weight"),
        )
        if limit:
            sel = sel.limit(limit)
        return sel
    except Exception as e:
        print(f"⚠ {name} ignoré : {e}")
        return None


def main():
    spark = build_spark_session(
        "MyDigitalTwin-BehavioralClustering",
        driver_memory="4g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        def read_table(name):
            return spark.read.format("delta").load(os.path.join(WAREHOUSE, name))

        sources = [
            safe_read(spark, "youtube_watch",    platform_name="youtube"),
            safe_read(spark, "google_searches",  platform_name="google",   weight_val=1.0),
            safe_read(spark, "google_chrome",    platform_name="chrome",   weight_val=1.0),
            safe_read(spark, "spotify_streams",  hour_col="listen_hour", weekday_col="listen_weekday",
                      platform_name="spotify"),
        ]

        # Netflix — no hour column → default to 21
        try:
            sources.append(
                read_table("netflix_views").select(
                    F.lit(21).cast(IntegerType()).alias("hour"),
                    F.col("watch_weekday").alias("weekday"),
                    F.lit("netflix").alias("platform"),
                    F.col("interaction_weight").cast(FloatType()).alias("weight"),
                )
            )
        except Exception as e:
            print(f"⚠ netflix_views ignoré : {e}")

        sources += [
            safe_read(spark, "tiktok_watch",     platform_name="tiktok",        limit=2000),
            safe_read(spark, "tiktok_likes",     platform_name="tiktok_likes",  limit=2000),
            safe_read(spark, "tiktok_searches",  platform_name="tiktok_search", weight_val=1.0, limit=1000),
            safe_read(spark, "instagram_likes",    platform_name="instagram",        limit=2000),
            safe_read(spark, "instagram_saved",    platform_name="instagram_saved",  limit=500),
            safe_read(spark, "instagram_comments", platform_name="instagram_comment",
                      weight_val=2.5, limit=500),
            safe_read(spark, "instagram_posts_viewed",   platform_name="ig_posts",   limit=2000),
            safe_read(spark, "instagram_videos_watched", platform_name="ig_videos",  limit=2000),
            safe_read(spark, "instagram_story_likes",    platform_name="ig_stories",
                      weight_val=1.5, limit=1000),
            safe_read(spark, "instagram_searches",       platform_name="ig_search",
                      weight_val=1.0, limit=500),
            safe_read(spark, "twitter_tweets",   platform_name="twitter"),
        ]

        valid_sources = [s for s in sources if s is not None]
        if not valid_sources:
            print("  ⚠ No behavioral data available — skip")
            return

        behavioral_raw = valid_sources[0]
        for s in valid_sources[1:]:
            behavioral_raw = behavioral_raw.union(s)

        behavioral_raw = behavioral_raw.filter(
            F.col("hour").isNotNull() & F.col("weekday").isNotNull()
        )
        print(f"Total events comportementaux : {behavioral_raw.count():,}")

        # ── B2. Platform time profiles ─────────────────────────────────────────
        profiled = behavioral_raw \
            .withColumn("slot",
                F.when((F.col("hour") >= 5)  & (F.col("hour") < 12), "morning")
                 .when((F.col("hour") >= 12) & (F.col("hour") < 18), "afternoon")
                 .when((F.col("hour") >= 18) & (F.col("hour") < 23), "evening")
                 .otherwise("night")
            ) \
            .withColumn("is_weekend", F.when(F.col("weekday") >= 6, 1.0).otherwise(0.0))

        platform_total = profiled.groupBy("platform").agg(
            F.count("*").alias("total"),
            F.round(F.avg("hour"), 2).alias("avg_hour"),
            F.round(F.avg("weekday"), 2).alias("avg_weekday"),
            (F.sum("is_weekend") / F.count("*")).alias("weekend_pct"),
        )

        slot_counts = profiled.groupBy("platform", "slot").agg(F.count("*").alias("cnt"))
        slot_pct = slot_counts.join(platform_total.select("platform", "total"), "platform") \
            .withColumn("pct", F.col("cnt") / F.col("total")) \
            .groupBy("platform") \
            .pivot("slot", ["morning", "afternoon", "evening", "night"]) \
            .agg(F.first("pct")) \
            .fillna(0.0)

        platform_profiles = slot_pct.join(platform_total, "platform")

        assembler = VectorAssembler(
            inputCols=["morning", "afternoon", "evening", "night", "weekend_pct"],
            outputCol="raw_features"
        )
        platform_profiles = assembler.transform(platform_profiles)

        scaler = StandardScaler(inputCol="raw_features", outputCol="features",
                                withMean=True, withStd=True)
        scaler_model = scaler.fit(platform_profiles)
        platform_profiles = scaler_model.transform(platform_profiles)

        # ── B3. KMeans ────────────────────────────────────────────────────────
        kmeans = KMeans(featuresCol="features", predictionCol="beh_cluster",
                        k=K_BEHAVIORAL, seed=42, maxIter=100)
        print(f"Training K-Means sur profils (k={K_BEHAVIORAL})...")
        km_model = kmeans.fit(platform_profiles)
        beh_df = km_model.transform(platform_profiles)

        evaluator = ClusteringEvaluator(featuresCol="features", predictionCol="beh_cluster")
        sil = evaluator.evaluate(beh_df)
        print(f"Silhouette Score (profils): {sil:.4f}")

        # ── B4. Cluster characterization ──────────────────────────────────────
        beh_cluster_info = []
        cluster_data = beh_df.groupBy("beh_cluster").agg(
            F.collect_list("platform").alias("platforms"),
            F.round(F.avg("avg_hour"), 1).alias("avg_hour"),
            F.round(F.avg("avg_weekday"), 1).alias("avg_weekday"),
            F.round(F.avg("weekend_pct"), 3).alias("weekend_pct"),
            F.sum("total").alias("item_count"),
        ).orderBy("beh_cluster").collect()

        for row in cluster_data:
            cid    = row["beh_cluster"]
            avg_h  = row["avg_hour"] or 0.0
            avg_wd = row["avg_weekday"] or 0.0
            count  = row["item_count"]
            plats  = row["platforms"]

            h = round(avg_h)
            if 5 <= h < 12:    period = "Matin"
            elif 12 <= h < 18: period = "Apres-midi"
            elif 18 <= h < 23: period = "Soir"
            else:              period = "Nuit"

            day_type = "Weekend" if row["weekend_pct"] > 0.35 else "Semaine"

            beh_cluster_info.append({
                "cluster_id":    cid,
                "item_count":    count,
                "avg_hour":      float(avg_h),
                "avg_weekday":   float(avg_wd),
                "time_period":   period,
                "day_type":      day_type,
                "top_platforms": plats,
            })
            print(f"[Cluster {cid}] {count:,} events | {period} . {day_type} | {plats}")

        # ── B6. Write behavioral_clusters ─────────────────────────────────────
        beh_rows = []
        for info in beh_cluster_info:
            cid = info["cluster_id"]
            beh_rows.append((
                cid,
                BEH_LABELS.get(cid, {}).get("label", f"Profil {cid}"),
                BEH_LABELS.get(cid, {}).get("emoji", "?"),
                float(info["avg_hour"]),
                float(info["avg_weekday"]),
                info["time_period"],
                info["day_type"],
                info["top_platforms"],
                info["item_count"]
            ))

        schema_beh = StructType([
            StructField("cluster_id",    IntegerType(), False),
            StructField("label",         StringType(),  False),
            StructField("emoji",         StringType(),  True),
            StructField("avg_hour",      DoubleType(),  True),
            StructField("avg_weekday",   DoubleType(),  True),
            StructField("time_period",   StringType(),  True),
            StructField("day_type",      StringType(),  True),
            StructField("top_platforms", ArrayType(StringType()), True),
            StructField("item_count",    LongType(),    True),
        ])

        beh_clusters_df = spark.createDataFrame(beh_rows, schema_beh)
        out_path = os.path.join(WAREHOUSE, "behavioral_clusters")

        if DeltaTable.isDeltaTable(spark, out_path):
            (
                DeltaTable.forPath(spark, out_path).alias("target")
                .merge(beh_clusters_df.alias("source"), "target.cluster_id = source.cluster_id")
                .whenMatchedUpdateAll()
                .whenNotMatchedInsertAll()
                .execute()
            )
        else:
            beh_clusters_df.write.format("delta").mode("overwrite").save(out_path)

        count = spark.read.format("delta").load(out_path).count()
        print(f"  ✓ behavioral_clusters — {count:,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
