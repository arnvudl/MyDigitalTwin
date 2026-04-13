"""
config.py — Configuration centrale du projet MyDigitalTwin
===========================================================
Un ami qui veut refaire le projet ne doit modifier QUE ce fichier.

Usage dans les notebooks :
    import sys, os
    sys.path.insert(0, os.path.abspath("../../.."))  # adapter selon la profondeur
    from config import WAREHOUSE, RAW_DATA, CLOSE_FRIENDS, SPOTIFY_ANCHOR_ARTISTS
"""

import os

# ── CHEMINS ────────────────────────────────────────────────────────────────────
# Changer PROJECT_ROOT si le projet est cloné ailleurs
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Chemin warehouse : priorité au chemin Docker, sinon local
WAREHOUSE = "/opt/spark/data/warehouse" if os.path.exists("/opt/spark/data/warehouse") \
            else os.path.join(PROJECT_ROOT, "data", "warehouse")

RAW_DATA  = os.path.join(PROJECT_ROOT, "data", "raw")

# ── GRAPHE SOCIAL ──────────────────────────────────────────────────────────────
# Noms des dossiers inbox Instagram (partie avant l'ID numérique)
# Ex : dossier 'clara_1093935518743724' → mettre 'clara'
CLOSE_FRIENDS = {
    "_louange___",
    "_paulinalambin",
    "adamvdd",
    "alice",
    "clara",
    "djyoyo",
    "erwan",
    "evan",
    "fafie",
    "fredfnmz",
    "gabi",
    "hugobernard",
    "jen",
    "jerome",
    "laura",
    "lenysoetaerts",
    "lou",
    "loulou",
    "maelle",
    "manonvandy",
    "mylene",
    "nana",
    "pilou",
    "romane",
    "sachou",
    "vic",
    "zo",
    "3li0tttt",
}

CLOSE_FRIENDS_MULTIPLIER = 2.0   # poids x2 pour les close friends dans le graphe
MIN_MESSAGES = 5                  # seuil pour exclure les inconnus / spams

# ── ALS — ANCRES DE PROFIL ────────────────────────────────────────────────────
# Artistes Spotify que tu aimes vraiment (utilisés pour construire ton profil ALS)
SPOTIFY_ANCHOR_ARTISTS = [
    "Damso", "Tiakola", "Travis Scott", "Bad Bunny",
    "Ninho", "Metro Boomin", "Ziak", "Gazo", "Freeze Corleone",
]

# Séries / films Netflix favoris (chargés aussi depuis src/scripts/03_als/top.md)
# Ajouter ici des titres exacts si top.md n'est pas disponible
NETFLIX_ANCHOR_TITLES = []  # laisser vide = utiliser top.md uniquement
