import pandera as pa
from pandera import Column, DataFrameSchema, Check

scenes = DataFrameSchema(
    {
        "photo_id": Column(str, nullable=False),
        "scene_id": Column(int, nullable=False),
        "path":     Column(str, nullable=False),
    },
    coerce=True,
)

scene_centroids = DataFrameSchema(
    {
        "scene_id":   Column(int, nullable=False),
        "scene_name": Column(str, nullable=False),
        "photo_count": Column(int, checks=Check.greater_than(0), nullable=False),
    },
    checks=Check(lambda df: df.duplicated(subset=["scene_id"]).sum() == 0,
                 error="Doublons sur scene_id"),
    coerce=True,
)

music_matches = DataFrameSchema(
    {
        "scene_id":   Column(int, nullable=False),
        "match_type": Column(str, checks=Check.isin(["temporal", "semantic", "manual", "fallback"]), nullable=False),
    },
    checks=Check(lambda df: df.duplicated(subset=["scene_id"]).sum() == 0,
                 error="Doublons sur scene_id"),
    coerce=True,
)
