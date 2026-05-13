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
from delta.tables import DeltaTable  # noqa: E402

RAW_PATH = os.path.join(PROCESSED_DATA, "NETFLIX", "NetflixViewingHistory.csv")
PARQUET_OUT = os.path.join(WAREHOUSE, "netflix_views")


def main():
    spark = build_spark_session("MyDigitalTwin - Netflix", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        if not os.path.exists(RAW_PATH):
            print(f"  ⚠ NetflixViewingHistory.csv introuvable — skip netflix")
            return

        df = spark.read.option("header", "true").option("encoding", "UTF-8").csv(RAW_PATH)

        # Date Netflix format M/D/YY
        df = df.withColumn("watch_date", F.to_date(F.col("Date"), "M/d/yy"))

        # Champs temporels
        df = df \
            .withColumn("watch_year", F.year("watch_date")) \
            .withColumn("watch_month", F.date_format("watch_date", "yyyy-MM")) \
            .withColumn("watch_weekday", F.dayofweek("watch_date")) \
            .withColumn("watch_week", F.weekofyear("watch_date"))

        # Série vs film
        df = df.withColumn(
            "content_type",
            F.when(F.col("Title").contains(":"), F.lit("series")).otherwise(F.lit("movie"))
        )

        # Titre de la série (avant le premier ':')
        df = df.withColumn(
            "show_title",
            F.when(
                F.col("content_type") == "series",
                F.trim(F.split(F.col("Title"), ":")[0])
            ).otherwise(F.col("Title"))
        )

        # Saison — regex français
        df = df.withColumn(
            "season",
            F.when(
                F.col("content_type") == "series",
                F.regexp_extract(F.col("Title"), r"Saison.(\d+)", 1)
            ).otherwise(F.lit(""))
        ).withColumn(
            "season",
            F.when(F.col("season") == "", F.lit(None).cast("int"))
            .otherwise(F.col("season").cast("int"))
        )

        # Titre de l'épisode (dernière partie après le dernier ':')
        df = df.withColumn(
            "episode_title",
            F.when(
                F.col("content_type") == "series",
                F.trim(F.element_at(F.split(F.col("Title"), ":"), -1))
            ).otherwise(F.lit(None))
        )

        # Renommer Title à la fin (après tous les withColumn qui l'utilisent)
        df = df.drop("Date").withColumnRenamed("Title", "raw_title")

        df_final = df.select(
            "raw_title", "show_title", "season", "episode_title",
            "content_type", "watch_date", "watch_year", "watch_month",
            "watch_weekday", "watch_week",
        )

        if DeltaTable.isDeltaTable(spark, PARQUET_OUT):
            DeltaTable.forPath(spark, PARQUET_OUT).alias("t").merge(
                df_final.alias("s"),
                "t.raw_title = s.raw_title AND t.watch_date = s.watch_date"
            ).whenNotMatchedInsertAll().execute()
        else:
            df_final.write.format("delta").save(PARQUET_OUT)

        count = spark.read.format("delta").load(PARQUET_OUT).count()
        print(f"  ✓ netflix_views — {count:,} lignes")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
