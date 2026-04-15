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

# ── CLONE CONVERSATIONNEL (04_clone) ──────────────────────────────────────────
LLM_DATA = os.path.join(PROJECT_ROOT, "data", "LLM_DATA")

# Chemin vers les DMs Instagram bruts
INSTAGRAM_INBOX = os.path.join(RAW_DATA, "INSTAGRAM", "your_instagram_activity", "messages", "inbox")

# Nom de l'utilisateur tel qu'il apparaît dans les JSON Instagram (sender_name)
INSTAGRAM_SENDER_NAME = "A R N A U D"

# Conversations sélectionnées pour le corpus du clone
# Clé = label lisible, valeur = liste de dossiers inbox (une conv peut avoir plusieurs dossiers)
# Ex : dossier 'evan_17940018788164627' dans data/raw/INSTAGRAM/.../inbox/
CLONE_CONVERSATIONS = {
    "djyoyo":     ["djyoyo_489918669070722"],
    "evan":       ["evan_17940018788164627"],
    "lou":        ["lou_1085673686153338"],
    "maelle":     ["maelle_17935615418472883"],
    "nana":       ["nana_18068525429472883"],
    "pilou":      ["pilou_519116326140721"],
    "laura":      ["laura_994708765285921"],
    "jen":        ["jen_945836883473151"],
    "alice":      ["alice_1204248657633025"],
    "loulou":     ["loulou_1188711339191134"],
    "laure":      ["laure_1094343585289278"],
    "fafie":      ["fafie_1121444139243508"],
    "gabi":       ["gabi_1275393733851743"],
    "manonvandy": ["manonvandy_1292074112190912"],
    "mylene":     ["mylene_802792480745084"],
    "ama":        ["ama_17970077582700199"],
    "eliott":     ["3li0tttt_17939266904472883"],
    "paulina":    ["_paulinalambin_824971795573896"],
    "celia":      ["celia_1366428128080987"],
    "vic":        ["vic_1114899529906843"],
    "romane":     ["romane_1357028805748638"],
}
