import pandera as pa
from pandera import Column, DataFrameSchema, Check

twitter_tweets = DataFrameSchema(
    {
        "tweet_id": Column(str, nullable=False),
    },
    checks=Check(lambda df: df.duplicated(subset=["tweet_id"]).sum() == 0,
                 error="Doublons sur tweet_id"),
    coerce=True,
)

twitter_likes = DataFrameSchema(
    {
        "tweet_id": Column(str, nullable=False),
    },
    checks=Check(lambda df: df.duplicated(subset=["tweet_id"]).sum() == 0,
                 error="Doublons sur tweet_id"),
    coerce=True,
)
