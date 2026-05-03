import pandera as pa
from pandera import Column, DataFrameSchema, Check

youtube_watch = DataFrameSchema(
    {
        "video_id":     Column(str, nullable=False),
        "timestamp_ms": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)

google_searches = DataFrameSchema(
    {
        "query":        Column(str, nullable=False),
        "timestamp_ms": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)
