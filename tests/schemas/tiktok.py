import pandera as pa
from pandera import Column, DataFrameSchema, Check

tiktok_watch = DataFrameSchema(
    {
        "video_id":     Column(str, nullable=False),
        "timestamp_ms": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)

tiktok_likes = DataFrameSchema(
    {
        "video_id":     Column(str, nullable=False),
        "timestamp_ms": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)

tiktok_messages_meta = DataFrameSchema(
    {
        "conv_id":      Column(str, nullable=False),
        "sender_anon":  Column(str, nullable=False),
        "timestamp_ms": Column(int, checks=Check.greater_than(0), nullable=False),
        "msg_type":     Column(str, nullable=False),
    },
    coerce=True,
)

tiktok_comments = DataFrameSchema(
    {
        "text":         Column(str, nullable=False),
        "timestamp_ms": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)
