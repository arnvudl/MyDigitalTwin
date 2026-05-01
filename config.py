"""
Central runtime configuration for MyDigitalTwin.

This file contains project paths and runtime settings.
Personal non-secret data belongs in config.yaml.
Secrets belong in .env.
"""

import os
import yaml
from dotenv import load_dotenv

# Load environment variables from .env file (for API keys and secrets)
load_dotenv()

# --- Base Paths ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Data root paths differ depending on the execution environment (local vs Docker)
_LOCAL_DATA_ROOT = os.path.join(PROJECT_ROOT, "data")
_APP_DATA_ROOT = "/app/data"         # Path inside the Dash dashboard container
_SPARK_DATA_ROOT = "/opt/spark/data" # Path inside the Spark container

def _pick_data_root() -> str:
    """Dynamically determine the root data directory based on the environment."""
    if os.path.exists(_APP_DATA_ROOT):
        return _APP_DATA_ROOT
    if os.path.exists(_SPARK_DATA_ROOT):
        return _SPARK_DATA_ROOT
    return _LOCAL_DATA_ROOT

DATA_ROOT = _pick_data_root()
APP_DATA_ROOT = _APP_DATA_ROOT
SPARK_DATA_ROOT = _SPARK_DATA_ROOT
LOCAL_DATA_ROOT = _LOCAL_DATA_ROOT

# --- Main Data Directories ---
# WAREHOUSE: Final, structured analytical tables (Parquet/Delta format)
WAREHOUSE = os.path.join(DATA_ROOT, "warehouse")

# PROCESSED_DATA: Cleaned and standardized GDPR exports (source of truth for notebooks)
PROCESSED_DATA = os.path.join(DATA_ROOT, "processed")

# LLM_DATA: Data generated for or by Large Language Models (e.g., clone training data)
LLM_DATA = os.path.join(DATA_ROOT, "LLM_DATA")

# INBOX_ROOT: Drop zone for raw, unextracted GDPR zip files
INBOX_ROOT = os.path.join(PROJECT_ROOT, "data", "inbox")

# --- Instagram Specific Paths ---
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

# --- Twitter/X Specific Paths ---
X_PERSONALIZATION_PATH = os.path.join(PROCESSED_DATA, "X", "data", "personalization.js")

# --- Derived Data Directories (Outputs) ---
SOCIAL_GRAPH_DIR = os.path.join(WAREHOUSE, "social_graph")
PHOTO_SORTING_DIR = os.path.join(INSTAGRAM_PROCESSED_ROOT, "CLIP_SORTING")
PHOTO_CLUSTERS_DIR = os.path.join(WAREHOUSE, "photo_clusters")
PHOTO_EMBEDDINGS_DIR = os.path.join(WAREHOUSE, "photo_embeddings")

# Source directories for photos to be analyzed by CLIP
PHOTO_SOURCE_DIRS = [
    os.path.join(INSTAGRAM_PROCESSED_ROOT, "media"),
    os.path.join(INSTAGRAM_PROCESSED_ROOT, "your_instagram_activity", "posts"),
    os.path.join(INSTAGRAM_PROCESSED_ROOT, "your_instagram_activity", "messages"),
]

# --- Memory Album ---
ALBUM_PHOTOS_DIR   = os.path.join(DATA_ROOT, "processed", "ALBUM")
MEMORY_ALBUM_DIR   = os.path.join(WAREHOUSE, "memory_album")
MODELS_CACHE_DIR   = os.path.join(DATA_ROOT, "models")   # cache HuggingFace (BLIP-2, OpenCLIP…)
MUSIC_LIBRARY_PATH = os.path.join(LLM_DATA, "music_library.json")

# --- Caches and Output Files ---
SPOTIFY_METADATA_CACHE_PATH = os.path.join(WAREHOUSE, "spotify_metadata.json")
TMDB_POSTER_CACHE_PATH = os.path.join(WAREHOUSE, "tmdb_poster_cache.json")

GEMINI_CORPUS_PATH = os.path.join(LLM_DATA, "gemini_corpus.txt")
GEMINI_SYSPROMPT_PATH = os.path.join(LLM_DATA, "SYS_PROMPT_ARNAUD")

# --- Dashboard Settings ---
APP_ASSETS_DIR = os.path.join(PROJECT_ROOT, "app", "assets")
DASH_HOST = os.getenv("DASH_HOST", "0.0.0.0")
DASH_PORT = int(os.getenv("DASH_PORT", "8050"))

# --- User Configuration (loaded from config.yaml) ---
_cfg_path = os.path.join(PROJECT_ROOT, "config.yaml")
if not os.path.exists(_cfg_path):
    raise FileNotFoundError(
        "\nconfig.yaml introuvable : "
        f"{_cfg_path}\n"
        "Copy config.yaml.example to config.yaml and fill your values.\n"
    )

with open(_cfg_path, encoding="utf-8") as _file:
    _cfg = yaml.safe_load(_file) or {}

# General User Info
INSTAGRAM_SENDER_NAME = _cfg.get("user", {}).get("instagram_sender_name", "")
INSTAGRAM_USERNAME = _cfg.get("user", {}).get("instagram_username", "")

# Social Graph Configuration
_social = _cfg.get("social", {})
CLOSE_FRIENDS = set(_social.get("close_friends", []))
CLOSE_FRIENDS_MULTIPLIER = float(_social.get("close_friends_multiplier", 2.0))
MIN_MESSAGES = int(_social.get("min_messages", 5))

# Spotify Topology Configuration
_spotify = _cfg.get("spotify", {})
SPOTIFY_ANCHOR_ARTISTS = _spotify.get("anchor_artists", [])
SPOTIFY_TOPOLOGY_THRESHOLD = int(_spotify.get("topology_stream_threshold", 5))

# Clone/LLM Configuration
CLONE_CONVERSATIONS = _cfg.get("clone", {}).get("conversations", {})

# Clustering Configuration
K_BEHAVIORAL = int(_cfg.get("clustering", {}).get("k_behavioral", 4))

# Content Category Keywords
CATEGORY_KEYWORDS: dict = _cfg.get("category_keywords", {})

# --- Spark ---
def build_spark_session(
    app_name: str,
    driver_memory: str = "4g",
    shuffle_partitions: int = 8,
    delta: bool = True,
    snappy: bool = False,
    master: str = "local[*]",
):
    """Crée ou récupère une SparkSession configurée pour le projet.

    Paramètres
    ----------
    app_name          : nom affiché dans la Spark UI
    driver_memory     : RAM allouée au driver  (ex: "4g", "6g", "8g")
    shuffle_partitions: nombre de partitions après un shuffle (réduire pour les petits datasets)
    delta             : active les extensions Delta Lake (lecture/écriture .delta)
    snappy            : active la compression Snappy pour le stockage Parquet
    master            : URL du cluster Spark ("local[*]" = tous les cœurs locaux)
    """
    from pyspark.sql import SparkSession
    builder = (SparkSession.builder
               .appName(app_name)
               .master(master)
               .config("spark.driver.memory", driver_memory)
               .config("spark.sql.shuffle.partitions", str(shuffle_partitions)))
    if delta:
        builder = (builder
                   .config("spark.sql.extensions",
                           "io.delta.sql.DeltaSparkSessionExtension")
                   .config("spark.sql.catalog.spark_catalog",
                           "org.apache.spark.sql.delta.catalog.DeltaCatalog"))
    if snappy:
        builder = builder.config("spark.sql.parquet.compression.codec", "snappy")
    return builder.getOrCreate()

# --- API Keys and Secrets (loaded from .env) ---
# NEVER hardcode these values here. They must remain in the ignored .env file.
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN", "")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
