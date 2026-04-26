"""
config.py — Configuration centrale MyDigitalTwin
=================================================
Ce fichier ne contient PAS de données personnelles.
Les données personnelles sont dans config.yaml (gitignored).
Les secrets sont dans .env (gitignored).

Usage dans les notebooks :
    import sys, os
    _d = os.path.abspath('')
    while not os.path.exists(os.path.join(_d, 'config.py')):
        _p = os.path.dirname(_d)
        if _p == _d: raise RuntimeError("config.py introuvable")
        _d = _p
    sys.path.insert(0, _d)
    from config import WAREHOUSE, PROCESSED_DATA, CLOSE_FRIENDS, ...
"""

import os
import yaml
from dotenv import load_dotenv

load_dotenv()

# ── Chemins (génériques — identiques pour tous les utilisateurs) ───────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

WAREHOUSE = "/opt/spark/data/warehouse" if os.path.exists("/opt/spark/data/warehouse") \
            else os.path.join(PROJECT_ROOT, "data", "warehouse")

PROCESSED_DATA = os.path.join(PROJECT_ROOT, "data", "processed")
RAW_DATA       = PROCESSED_DATA   # alias rétrocompatibilité notebooks

LLM_DATA          = os.path.join(PROJECT_ROOT, "data", "LLM_DATA")
INSTAGRAM_INBOX   = os.path.join(PROCESSED_DATA, "INSTAGRAM",
                                  "your_instagram_activity", "messages", "inbox")

# ── Chargement config.yaml (données personnelles) ─────────────────────────────
_cfg_path = os.path.join(PROJECT_ROOT, "config.yaml")

if not os.path.exists(_cfg_path):
    raise FileNotFoundError(
        f"\nconfig.yaml introuvable : {_cfg_path}\n"
        "→ Copier config.yaml.example → config.yaml et remplir vos données.\n"
        "  cp config.yaml.example config.yaml"
    )

with open(_cfg_path, encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)

# ── Identité ──────────────────────────────────────────────────────────────────
INSTAGRAM_SENDER_NAME = _cfg.get("user", {}).get("instagram_sender_name", "")

# ── Graphe social ─────────────────────────────────────────────────────────────
_social                 = _cfg.get("social", {})
CLOSE_FRIENDS           = set(_social.get("close_friends", []))
CLOSE_FRIENDS_MULTIPLIER = float(_social.get("close_friends_multiplier", 2.0))
MIN_MESSAGES            = int(_social.get("min_messages", 5))

# ── Spotify ───────────────────────────────────────────────────────────────────
_spotify                   = _cfg.get("spotify", {})
SPOTIFY_ANCHOR_ARTISTS     = _spotify.get("anchor_artists", [])
SPOTIFY_TOPOLOGY_THRESHOLD = int(_spotify.get("topology_stream_threshold", 5))

# ── Clone conversationnel ─────────────────────────────────────────────────────
CLONE_CONVERSATIONS = _cfg.get("clone", {}).get("conversations", {})

# ── Secrets (depuis .env) ─────────────────────────────────────────────────────
TMDB_API_KEY         = os.getenv("TMDB_API_KEY", "")
SPOTIFY_CLIENT_ID    = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
