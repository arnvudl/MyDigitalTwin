"""
Tests de qualité de données sur le warehouse (Delta Lake).
Utilise Pandera pour valider les schémas et les contraintes métier.
Les tables sont lues via pandas (pd.read_parquet) — pas de SparkSession requise.
"""
import os
import sys
import datetime
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from config import WAREHOUSE, MEMORY_ALBUM_DIR

try:
    import pandera as pa
    HAS_PANDERA = True
except ImportError:
    HAS_PANDERA = False

pytestmark = [
    pytest.mark.data_quality,
    pytest.mark.skipif(not HAS_PANDERA, reason="pandera n'est pas installé"),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load(table_path: str) -> pd.DataFrame:
    """Lit un dossier Delta/Parquet en pandas. Skip si absent."""
    if not os.path.exists(table_path):
        pytest.skip(f"Table absente (ingestion non exécutée) : {table_path}")
    return pd.read_parquet(table_path)


# ── Spotify ────────────────────────────────────────────────────────────────────

def test_spotify_streams_schema():
    from tests.schemas.spotify import spotify_streams
    df = _load(os.path.join(WAREHOUSE, "spotify_streams"))
    assert len(df) > 1_000, "spotify_streams : volume anormalement faible (<1000 lignes)."
    # Invariant temporel : pas d'écoutes dans le futur (marge 1j)
    now = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    max_ts = pd.to_datetime(df["listen_ts"]).max().replace(tzinfo=None)
    assert max_ts <= now, f"spotify_streams : écoutes dans le futur ({max_ts})."
    spotify_streams.validate(df)


def test_spotify_liked_songs_schema():
    from tests.schemas.spotify import spotify_liked_songs
    df = _load(os.path.join(WAREHOUSE, "spotify_liked_songs"))
    spotify_liked_songs.validate(df)


def test_spotify_playlists_schema():
    from tests.schemas.spotify import spotify_playlists
    df = _load(os.path.join(WAREHOUSE, "spotify_playlists"))
    spotify_playlists.validate(df)


def test_spotify_searches_schema():
    from tests.schemas.spotify import spotify_searches
    df = _load(os.path.join(WAREHOUSE, "spotify_searches"))
    spotify_searches.validate(df)


# ── Netflix ────────────────────────────────────────────────────────────────────

def test_netflix_views_schema():
    from tests.schemas.netflix import netflix_views
    df = _load(os.path.join(WAREHOUSE, "netflix_views"))
    assert len(df) > 100, "netflix_views : volume anormalement faible (<100 lignes)."
    netflix_views.validate(df)


# ── Instagram ─────────────────────────────────────────────────────────────────

def test_instagram_messages_meta_schema():
    from tests.schemas.instagram import instagram_messages_meta
    df = _load(os.path.join(WAREHOUSE, "instagram_messages_meta"))
    instagram_messages_meta.validate(df)


def test_instagram_comments_schema():
    from tests.schemas.instagram import instagram_comments
    df = _load(os.path.join(WAREHOUSE, "instagram_comments"))
    instagram_comments.validate(df)


def test_instagram_likes_schema():
    from tests.schemas.instagram import instagram_likes
    df = _load(os.path.join(WAREHOUSE, "instagram_likes"))
    instagram_likes.validate(df)


def test_instagram_saved_schema():
    from tests.schemas.instagram import instagram_saved
    df = _load(os.path.join(WAREHOUSE, "instagram_saved"))
    instagram_saved.validate(df)


def test_instagram_searches_schema():
    from tests.schemas.instagram import instagram_searches
    df = _load(os.path.join(WAREHOUSE, "instagram_searches"))
    instagram_searches.validate(df)


# ── TikTok ─────────────────────────────────────────────────────────────────────

def test_tiktok_watch_schema():
    from tests.schemas.tiktok import tiktok_watch
    df = _load(os.path.join(WAREHOUSE, "tiktok_watch"))
    tiktok_watch.validate(df)


def test_tiktok_likes_schema():
    from tests.schemas.tiktok import tiktok_likes
    df = _load(os.path.join(WAREHOUSE, "tiktok_likes"))
    tiktok_likes.validate(df)


def test_tiktok_messages_meta_schema():
    from tests.schemas.tiktok import tiktok_messages_meta
    df = _load(os.path.join(WAREHOUSE, "tiktok_messages_meta"))
    tiktok_messages_meta.validate(df)


def test_tiktok_comments_schema():
    from tests.schemas.tiktok import tiktok_comments
    df = _load(os.path.join(WAREHOUSE, "tiktok_comments"))
    tiktok_comments.validate(df)


# ── Twitter ────────────────────────────────────────────────────────────────────

def test_twitter_tweets_schema():
    from tests.schemas.twitter import twitter_tweets
    df = _load(os.path.join(WAREHOUSE, "twitter_tweets"))
    twitter_tweets.validate(df)


def test_twitter_likes_schema():
    from tests.schemas.twitter import twitter_likes
    df = _load(os.path.join(WAREHOUSE, "twitter_likes"))
    twitter_likes.validate(df)


# ── Google / YouTube ──────────────────────────────────────────────────────────

def test_youtube_watch_schema():
    from tests.schemas.google import youtube_watch
    df = _load(os.path.join(WAREHOUSE, "youtube_watch"))
    youtube_watch.validate(df)


def test_google_searches_schema():
    from tests.schemas.google import google_searches
    df = _load(os.path.join(WAREHOUSE, "google_searches"))
    google_searches.validate(df)


# ── Memory Album ──────────────────────────────────────────────────────────────

def test_memory_album_scenes_schema():
    from tests.schemas.memory_album import scenes
    df = _load(os.path.join(MEMORY_ALBUM_DIR, "scenes"))
    scenes.validate(df)


def test_memory_album_centroids_schema():
    from tests.schemas.memory_album import scene_centroids
    df = _load(os.path.join(MEMORY_ALBUM_DIR, "scene_centroids"))
    scene_centroids.validate(df)


def test_memory_album_music_matches_schema():
    from tests.schemas.memory_album import music_matches
    df = _load(os.path.join(MEMORY_ALBUM_DIR, "music_matches"))
    music_matches.validate(df)


# ── Cross-table ────────────────────────────────────────────────────────────────

def test_cross_table_date_consistency():
    """Spotify et Netflix couvrent chacun plus d'un an d'historique."""
    spotify_path = os.path.join(WAREHOUSE, "spotify_streams")
    netflix_path = os.path.join(WAREHOUSE, "netflix_views")
    if not os.path.exists(spotify_path) or not os.path.exists(netflix_path):
        pytest.skip("Une ou plusieurs tables absentes.")

    spotify_df = pd.read_parquet(spotify_path)
    netflix_df = pd.read_parquet(netflix_path)

    spotify_range = pd.to_datetime(spotify_df["listen_ts"]).max() - pd.to_datetime(spotify_df["listen_ts"]).min()
    netflix_range = pd.to_datetime(netflix_df["watch_date"]).max() - pd.to_datetime(netflix_df["watch_date"]).min()

    assert spotify_range.days >= 365, "Historique Spotify < 1 an."
    assert netflix_range.days >= 365, "Historique Netflix < 1 an."
