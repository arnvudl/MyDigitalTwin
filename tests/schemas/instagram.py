import pandera as pa
from pandera import Column, DataFrameSchema, Check

instagram_messages_meta = DataFrameSchema(
    {
        "conv_id":      Column(str, nullable=False),
        "sender_anon":  Column(str, nullable=False),
        "timestamp_ms": Column(int, checks=Check.greater_than(0), nullable=False),
        "msg_type":     Column(str, nullable=False),
    },
    coerce=True,
)

instagram_comments = DataFrameSchema(
    {
        "text":      Column(str, nullable=False),
        "timestamp": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)

instagram_likes = DataFrameSchema(
    {
        "post_url":  Column(str, nullable=False),
        "timestamp": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)

instagram_saved = DataFrameSchema(
    {
        "post_href": Column(str, nullable=False),
        "timestamp": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)

instagram_searches = DataFrameSchema(
    {
        "query":     Column(str, nullable=False),
        "timestamp": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    coerce=True,
)
