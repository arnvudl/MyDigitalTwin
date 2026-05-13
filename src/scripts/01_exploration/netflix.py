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
    IntegerType,
)
from delta.tables import DeltaTable  # noqa: E402
import glob  # noqa: E402


NETFLIX_DIR = os.path.join(PROCESSED_DATA, "NETFLIX")


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
    spark = build_spark_session("MyDigitalTwin - Netflix", driver_memory="4g", shuffle_partitions=8)
    spark.sparkContext.setLogLevel("WARN")
    try:
        csv_files = (
            glob.glob(os.path.join(NETFLIX_DIR, "**", "NetflixViewingHistory.csv"), recursive=True)
            or glob.glob(os.path.join(NETFLIX_DIR, "**", "ViewingActivity.csv"), recursive=True)
        )
        if not csv_files:
            print("  ⚠ NetflixViewingHistory.csv introuvable — skip netflix")
            return

        schema = StructType([
            StructField("Title", StringType()),
            StructField("Date", StringType()),
        ])

        df = spark.read.option("header", "true").schema(schema).csv(csv_files[0])

        # Parse date from "M/d/yy" format
        df = df.withColumn("event_date", F.to_date(F.col("Date"), "M/d/yy"))

        # Series vs movie: series have ":" in title (Season/Episode separator)
        df = df.withColumn("content_type", F.when(F.col("Title").contains(":"), F.lit("series")).otherwise(F.lit("movie")))

        # For series, extract show_title, season, episode_title
        df = (
            df.withColumn("parts", F.split(F.col("Title"), ": "))
              .withColumn("show_title", F.when(F.col("content_type") == "series", F.col("parts").getItem(0)).otherwise(F.col("Title")))
              .withColumn("season_episode", F.when(F.col("content_type") == "series", F.col("parts").getItem(1)).otherwise(F.lit(None)))
              .withColumn("episode_title", F.when(F.col("content_type") == "series", F.col("parts").getItem(2)).otherwise(F.lit(None)))
              .withColumn("season", F.when(
                  F.col("season_episode").isNotNull(),
                  F.regexp_extract(F.col("season_episode"), r"(?:Season|Saison)\s*(\d+)", 1).cast(IntegerType())
              ).otherwise(F.lit(None).cast(IntegerType())))
              .drop("parts", "season_episode")
        )

        df = (
            df.withColumn("title", F.col("Title"))
              .withColumn("platform", F.lit("netflix"))
              .withColumn("event_year", F.year("event_date"))
              .withColumn("event_month", F.month("event_date"))
              .withColumn("event_weekday", F.dayofweek("event_date"))
              .select(
                  "title", "show_title", "season", "episode_title",
                  "content_type", "event_date", "event_year", "event_month", "event_weekday",
                  "platform"
              )
        )

        _merge_table(spark, df, "netflix_views", "t.title = s.title AND t.event_date = s.event_date")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
