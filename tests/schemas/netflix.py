import pandera as pa
from pandera import Column, DataFrameSchema, Check

netflix_views = DataFrameSchema(
    {
        "show_title":   Column(str, nullable=False),
        "watch_date":   Column("datetime64[ns]", nullable=False),
        "content_type": Column(str, checks=Check.isin(["series", "movie"]), nullable=False),
    },
    checks=Check(lambda df: df.duplicated(subset=["show_title", "watch_date"]).sum() == 0,
                 error="Doublons sur la clé (show_title, watch_date)"),
    coerce=True,
)
