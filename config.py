"""
Central runtime configuration for MyDigitalTwin.

This file contains project paths and runtime settings.
Personal non-secret data belongs in config.yaml.
Secrets belong in .env.
"""

import os

import yaml
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

_LOCAL_DATA_ROOT = os.path.join(PROJECT_ROOT, "data")
_APP_DATA_ROOT = "/app/data"
_SPARK_DATA_ROOT = "/opt/spark/data"


def _pick_data_root() -> str:
    if os.path.exists(_APP_DATA_ROOT):
        return _APP_DATA_ROOT
    if os.path.exists(_SPARK_DATA_ROOT):
        return _SPARK_DATA_ROOT
    return _LOCAL_DATA_ROOT


DATA_ROOT = _pick_data_root()
APP_DATA_ROOT = _APP_DATA_ROOT
SPARK_DATA_ROOT = _SPARK_DATA_ROOT
LOCAL_DATA_ROOT = _LOCAL_DATA_ROOT

WAREHOUSE = os.path.join(DATA_ROOT, "warehouse")
PROCESSED_DATA = os.path.join(DATA_ROOT, "processed")
RAW_DATA = PROCESSED_DATA  # Legacy alias kept for old notebooks.
LLM_DATA = os.path.join(DATA_ROOT, "LLM_DATA")

INBOX_ROOT = os.path.join(PROJECT_ROOT, "data", "inbox")

INSTAGRAM_PROCESSED_ROOT = os.path.join(PROCESSED_DATA, "INSTAGRAM")
INSTAGRAM_INBOX = os.path.join(
    INSTAGRAM_PROCESSED_ROOT,
    "your_instagram_activity",
    "messages",
    "inbox",
)
INSTAGRAM_TOPICS_PATH = os.path.join(
    INSTAGRAM_PROCESSED_ROOT,
    "preferences",
    "your_topics",
    "recommended_topics.json",
)
X_PERSONALIZATION_PATH = os.path.join(PROCESSED_DATA, "X", "data", "personalization.js")

SOCIAL_GRAPH_DIR = os.path.join(WAREHOUSE, "social_graph")
PHOTO_SORTING_DIR = os.path.join(INSTAGRAM_PROCESSED_ROOT, "CLIP_SORTING")
PHOTO_CLUSTERS_DIR = os.path.join(WAREHOUSE, "photo_clusters")
PHOTO_EMBEDDINGS_DIR = os.path.join(WAREHOUSE, "photo_embeddings")
PHOTO_SOURCE_DIRS = [
    os.path.join(INSTAGRAM_PROCESSED_ROOT, "media"),
    os.path.join(INSTAGRAM_PROCESSED_ROOT, "your_instagram_activity", "posts"),
    os.path.join(INSTAGRAM_PROCESSED_ROOT, "your_instagram_activity", "messages"),
]

SPOTIFY_METADATA_CACHE_PATH = os.path.join(WAREHOUSE, "spotify_metadata.json")
TMDB_POSTER_CACHE_PATH = os.path.join(WAREHOUSE, "tmdb_poster_cache.json")
GEMINI_CORPUS_PATH = os.path.join(LLM_DATA, "gemini_corpus.txt")
GEMINI_SYSPROMPT_PATH = os.path.join(LLM_DATA, "SYS_PROMPT_ARNAUD")

APP_ASSETS_DIR = os.path.join(PROJECT_ROOT, "app", "assets")
DASH_HOST = os.getenv("DASH_HOST", "0.0.0.0")
DASH_PORT = int(os.getenv("DASH_PORT", "8050"))

_cfg_path = os.path.join(PROJECT_ROOT, "config.yaml")
if not os.path.exists(_cfg_path):
    raise FileNotFoundError(
        "\nconfig.yaml introuvable : "
        f"{_cfg_path}\n"
        "Copy config.yaml.example to config.yaml and fill your values.\n"
    )

with open(_cfg_path, encoding="utf-8") as _file:
    _cfg = yaml.safe_load(_file) or {}

INSTAGRAM_SENDER_NAME = _cfg.get("user", {}).get("instagram_sender_name", "")
INSTAGRAM_USERNAME = _cfg.get("user", {}).get("instagram_username", "")

_social = _cfg.get("social", {})
CLOSE_FRIENDS = set(_social.get("close_friends", []))
CLOSE_FRIENDS_MULTIPLIER = float(_social.get("close_friends_multiplier", 2.0))
MIN_MESSAGES = int(_social.get("min_messages", 5))

_spotify = _cfg.get("spotify", {})
SPOTIFY_ANCHOR_ARTISTS = _spotify.get("anchor_artists", [])
SPOTIFY_TOPOLOGY_THRESHOLD = int(_spotify.get("topology_stream_threshold", 5))

CLONE_CONVERSATIONS = _cfg.get("clone", {}).get("conversations", {})

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN", "")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
