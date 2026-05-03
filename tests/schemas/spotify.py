import pandera as pa
from pandera import Column, DataFrameSchema, Check

spotify_streams = DataFrameSchema(
    {
        "trackName":  Column(str,   nullable=False),
        "artistName": Column(str,   nullable=False),
        "listen_ts":  Column("datetime64[ns]", nullable=False),
        "msPlayed":   Column(int,   checks=Check.greater_than_or_equal_to(30_000)),
    },
    checks=Check(lambda df: df.duplicated(subset=["trackName", "artistName", "listen_ts"]).sum() == 0,
                 error="Doublons sur la clé (trackName, artistName, listen_ts)"),
    coerce=True,
)

spotify_liked_songs = DataFrameSchema(
    {
        "trackUri":  Column(str, nullable=False),
        "trackName": Column(str, nullable=False),
    },
    checks=Check(lambda df: df.duplicated(subset=["trackUri"]).sum() == 0,
                 error="Doublons sur trackUri"),
    coerce=True,
)

spotify_playlists = DataFrameSchema(
    {
        "playlistName": Column(str, nullable=False),
        "trackUri":     Column(str, nullable=False),
    },
    coerce=True,
)

spotify_searches = DataFrameSchema(
    {
        "query":     Column(str, nullable=False),
        "search_ts": Column("datetime64[ns]", nullable=False),
    },
    coerce=True,
)
