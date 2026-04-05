import json
import math
import os
from functools import lru_cache
import re

import pandas as pd
from dash import Input, Output, callback, html, dcc, ALL

# ─── CONFIG ──────────────────────────────────────────────────────────────────
# On vérifie si on est dans Docker (où les dossiers sont montés à la racine /app/data et /app/warehouse)
# ou en local (où les dossiers sont dans le répertoire courant).
if os.path.exists("/app/warehouse"):
    DELTA_BASE = "/app/warehouse"
    IG_TOPICS_PATH = "/app/data/raw/INSTAGRAM/preferences/your_topics/recommended_topics.json"
    X_PERSONALIZATION_PATH = "/app/data/raw/X/data/personalization.js"
else:
    DELTA_BASE = "warehouse"
    IG_TOPICS_PATH = "data/raw/INSTAGRAM/preferences/your_topics/recommended_topics.json"
    X_PERSONALIZATION_PATH = "data/raw/X/data/personalization.js"

CATEGORY_KEYWORDS = {
    "⚽ Sport": [
        "football", "soccer", "nba", "league", "match", "goal", "player", "arsenal", "champions",
        "fifa", "ligue", "rugby", "tennis", "basketball", "sport", "ballon d'or", "ucl", "premier league",
        "ufc", "mma", "boxing", "gym", "fitness", "workout", "calisthenics", "training", "nfl",
        "olympics", "swimming", "cycling", "padel", "volleyball"
    ],
    "🏎️ Auto/Moto": [
        "car", "auto", "voiture", "porsche", "ferrari", "lamborghini", "bmw", "mercedes", "audi",
        "tesla", "f1", "formula 1", "supercar", "hypercar", "drift", "tuning", "engine", "v8",
        "v12", "electric vehicle", "motorsport", "motorcycle", "moto", "yamaha", "kawasaki",
        "mclaren", "bugatti", "aston martin", "jdm", "nissan", "toyota", "supra", "rb26",
        "porsche 911", "rs6", "amg", "m performance", "ducati", "harley", "grand prix"
    ],
    "🎵 Musique": [
        "music", "song", "artist", "rap", "album", "track", "beat", "drill", "trap", "afrobeat",
        "afropop", "rnb", "r&b", "hip", "hop", "streaming", "spotify", "playlist", "concert",
        "festival", "lyrics", "producer", "instrumental", "pop", "rock", "techno", "house",
        "electro", "low fi", "lo-fi", "jazz", "synth", "dj", "remix", "type beat", "soundcloud"
    ],
    "💻 Tech": [
        "python", "code", "data", "dev", "javascript", "api", "ai", "software", "tech",
        "developer", "engineering", "science", "consumer tech", "technology", "equipment",
        "artificial intelligence", "machine learning", "deep learning", "nlp", "llm", "pytorch",
        "tensorflow", "backend", "frontend", "fullstack", "react", "github", "docker", "kubernetes",
        "cloud", "aws", "cybersecurity", "linux", "open source", "startup", "computer science",
        "rust", "typescript", "chatgpt", "openai", "gpu", "nvidia", "cuda"
    ],
    "🎬 Cinéma/Séries": [
        "netflix", "film", "série", "movie", "episode", "cinema", "watch", "trailer", "season",
        "tv", "show", "streaming", "anime", "manga", "crunchyroll", "hbo", "prime video",
        "disney+", "marvel", "dc comics", "star wars", "oscars", "documentary", "horror",
        "scifi", "animation", "otaku", "ghibli"
    ],
    "🎮 Gaming": [
        "game", "gaming", "play", "xbox", "ps5", "steam", "minecraft", "fortnite", "esport",
        "gamer", "action game", "video game", "ar/vr", "nintendo", "switch", "twitch",
        "discord", "multiplayer", "rpg", "fps", "roblox", "league of legends", "valorant",
        "warzone", "gta", "elden ring", "zelda", "playstation", "controller", "pc master race"
    ],
    "🌍 Actu/Société": [
        "news", "actu", "society", "monde", "france", "afrique", "africa", "senegal",
        "politique", "cup of nations", "environment", "ecology", "climate", "space",
        "nasa", "spacex", "economy", "finance", "crypto", "bitcoin", "ethereum",
        "blockchain", "stock market", "history", "philosophy", "culture", "university"
    ],
    "🛍️ Shopping": [
        "amazon", "shop", "product", "électronique", "brand", "adidas", "nike", "fashion",
        "style", "luxury", "streetwear", "sneakers", "yeezy", "jordan", "clothes", "outfit",
        "ecommerce", "unboxing", "skincare", "watches", "apple", "iphone", "samsung",
        "gadget", "deals", "dior", "louis vuitton", "stussy", "vintage"
    ],
    "📸 Photo/Créa": [
        "photo", "photography", "design", "creative", "art", "visual", "camera", "image",
        "graphic", "illustration", "photoshop", "lightroom", "editing", "video production",
        "content creation", "youtube", "tiktok", "reels", "architecture", "interior design",
        "digital art", "ui/ux", "portfolio", "3d modeling", "blender", "canva"
    ],
}

# ─── DELTA READER ────────────────────────────────────────────────────────────
def _read_delta(table_name: str, cols: list) -> pd.DataFrame:
    table_path = os.path.join(DELTA_BASE, table_name)
    if not os.path.exists(table_path):
        return pd.DataFrame(columns=cols)
    
    # Lecture des fichiers parquet au lieu du format delta _delta_log (car la librairie delta prend trop de place pour le web container)
    files = [
        os.path.join(table_path, f)
        for f in os.listdir(table_path)
        if f.endswith(".parquet") and not f.startswith(".")
    ]
    if not files:
        return pd.DataFrame(columns=cols)
    dfs = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            existing = [c for c in cols if c in df.columns]
            if existing:
                dfs.append(df[existing])
        except Exception as e:
            print(f"Error reading {f}: {e}")
            pass
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(columns=cols)

# ─── INTEREST PROFILES (K-Means output) ──────────────────────────────────────
@lru_cache(maxsize=1)
def load_interest_profiles() -> dict | None:
    """
    Charge les profils K-Means depuis warehouse/interest_profiles.
    Retourne None si le notebook n'a pas encore tourné (fallback sur keyword matching).
    """
    df = _read_delta("interest_profiles", [
        "hybrid_label", "emoji", "keywords", "sample_items", "item_count", "time_period"
    ])
    if df.empty:
        return None

    scores, examples = {}, {}
    for _, row in df.iterrows():
        label    = row.get("hybrid_label") or "Inconnu"
        kws      = list(row["keywords"])   if isinstance(row.get("keywords"),   (list, object)) else []
        samples  = list(row["sample_items"]) if isinstance(row.get("sample_items"), (list, object)) else []
        count    = int(row.get("item_count") or 0)
        scores[label]   = count
        examples[label] = (kws + samples)[:15]

    sorted_scores = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))
    return {
        "scores":     sorted_scores,
        "examples":   examples,
        "raw_topics": [],
        "source":     "kmeans",
    }


# ─── KEYWORDS (fallback si K-Means pas encore disponible) ────────────────────
@lru_cache(maxsize=1)
def load_all_keywords() -> dict:
    ig_topics, x_interests = [], []

    if os.path.exists(IG_TOPICS_PATH):
        try:
            with open(IG_TOPICS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("topics_your_topics", []):
                val = item.get("string_map_data", {}).get("Nom", {}).get("value", "")
                if val:
                    ig_topics.append(val)
        except:
            pass

    if os.path.exists(X_PERSONALIZATION_PATH):
        try:
            with open(X_PERSONALIZATION_PATH, encoding="utf-8") as f:
                raw = f.read()
            if raw.strip().startswith("window."):
                raw = raw[raw.index("=") + 1:].strip()
            data = json.loads(raw)
            for entry in data:
                interests = entry.get("p13nData", {}).get("interests", {}).get("interests", [])
                for i in interests:
                    name = i.get("name", "")
                    if name and not i.get("isDisabled", False):
                        x_interests.append(name)
        except:
            pass

    all_topics = ig_topics + x_interests

    category_scores  = {}
    category_examples = {}
    
    used_topics = set()

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        found = []
        for topic in all_topics:
            topic_lower = topic.lower()
            
            if topic_lower in used_topics:
                continue

            is_match = False
            for kw in keywords:
                # 1. Correspondance exacte
                if topic_lower == kw:
                    is_match = True
                    break
                
                # 2. Utiliser \b pour forcer la correspondance sur un mot entier
                # On tolère les tirets, underscores ou espaces autour
                # Pour éviter que "Art" matche "Artificial Intelligence" ou "Mikel Arteta"
                pattern = r'(?:\b|_|-| )' + re.escape(kw) + r'(?:\b|_|-| )'
                if re.search(pattern, topic_lower):
                    is_match = True
                    break
                    
            if is_match:
                score += 1
                clean = topic.strip()
                if clean not in found and len(clean) <= 35:
                    found.append(clean)
                used_topics.add(topic_lower)
        
        category_scores[cat] = score
        category_examples[cat] = found[:15]

    sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "scores":     {k: v for k, v in sorted_cats},
        "examples":   category_examples,
        "raw_topics": all_topics,
        "source":     "keywords",
    }


def load_interests() -> dict:
    """Point d'entrée unique : K-Means en priorité, keyword matching en fallback."""
    profiles = load_interest_profiles()
    if profiles is not None:
        return profiles
    return load_all_keywords()

# ─── STATS ───────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def compute_stats() -> dict:
    stats = {}
    
    # Spotify - The column is 'artistName' 
    df_spotify = _read_delta("spotify_streams", ["artistName"])
    stats["artistes"] = df_spotify["artistName"].nunique() if not df_spotify.empty else 0

    # Netflix - The column is 'show_title' 
    df_netflix = _read_delta("netflix_views", ["show_title"])
    stats["films"] = len(df_netflix) if not df_netflix.empty else 0

    # Google - The column is 'query'
    df_google = _read_delta("google_searches", ["query"])
    stats["recherches"] = len(df_google) if not df_google.empty else 0

    # Twitter - The column is 'tweet_id'
    df_twitter = _read_delta("twitter_tweets", ["tweet_id"])
    stats["tweets"] = len(df_twitter) if not df_twitter.empty else 0

    return stats

# ─── TAG POSITIONING (left/top absolus, centre = 380px) ──────────────────────
CENTER = 380  # moitié de 760px

def _pos(angle_deg: float, radius: float) -> dict:
    rad = math.radians(angle_deg)
    x = CENTER + radius * math.cos(rad)
    y = CENTER + radius * math.sin(rad)
    return {"left": f"{x}px", "top": f"{y}px"}

def build_orbit_tags(data: dict) -> list:
    scores   = data["scores"]
    examples = data["examples"]
    cats     = list(scores.keys())
    tags     = []

    # ── Anneau 1 : top 6 catégories
    ring1 = cats[:6]
    for i, cat in enumerate(ring1):
        angle = (360 / len(ring1)) * i - 90
        style = _pos(angle, 170)
        tags.append(html.Div(
            id={"type": "orbit-tag", "index": cat},
            className="orbit-tag tag-r1",
            style=style,
            children=[cat],
            n_clicks=0,
        ))

    # ── Anneau 2 : 2 exemples par top-4 catégorie
    ring2_items = []
    for cat in ring1[:4]:
        for ex in examples.get(cat, [])[:2]:
            ring2_items.append((ex, cat))

    for i, (label, _) in enumerate(ring2_items[:10]):
        angle = (360 / max(len(ring2_items), 1)) * i - 70
        style = _pos(angle, 255)
        # On passe directement le nom de l'exemple en ID pour que le callback le reconnaisse !
        tags.append(html.Div(
            id={"type": "orbit-tag", "index": label},
            className="orbit-tag tag-r2",
            style=style,
            children=[label],
            n_clicks=0,
        ))

    # ── Anneau 3 : catégories secondaires + exemples épars
    ring3_items = []
    # On ajoute d'abord les catégories secondaires en tant que telles (pour avoir le bon comportement au clic)
    for cat in cats[6:]:
        ring3_items.append((cat, True))
    
    # Puis on ajoute des exemples supplémentaires
    for cat in ring1[:3]:
        for ex in examples.get(cat, [])[2:4]:
            ring3_items.append((ex, False))

    for i, (label, is_cat) in enumerate(ring3_items[:12]):
        angle = (360 / max(len(ring3_items), 1)) * i - 50
        style = _pos(angle, 340)
        tags.append(html.Div(
            id={"type": "orbit-tag", "index": label},
            className="orbit-tag tag-r3",
            style=style,
            children=[label],
            n_clicks=0,
        ))

    return tags

# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    data  = load_interests()
    stats = compute_stats()
    tags  = build_orbit_tags(data)

    stats_cards = [
        {"icon": "🎵", "value": f"{stats['artistes']:,}",    "label": "Artistes écoutés"},
        {"icon": "🎬", "value": f"{stats['films']:,}",        "label": "Contenus Netflix"},
        {"icon": "🔍", "value": f"{stats['recherches']:,}",   "label": "Recherches Google"},
        {"icon": "🐦", "value": f"{stats['tweets']:,}",       "label": "Tweets postés"},
        {"icon": "📱", "value": str(len(data["scores"])),     "label": "Centres d'intérêt"},
    ]

    return html.Div(className="page-wrapper", children=[
        html.Div(className="home-container", children=[

            # Hero
            html.Div(className="home-hero", children=[
                html.P("Données personnelles • 2022–2026", className="home-hero-label"),
                html.H1(html.Span(["My ", html.Em("Digital"), " Twin"]), className="home-hero-title"),
                html.P("Une radiographie de qui tu es, à travers tes données.", className="home-hero-sub"),
            ]),

            # Orbit
            html.Div(className="orbit-section", children=[
                html.Div(className="orbit-ring orbit-ring-4"),
                html.Div(className="orbit-ring orbit-ring-3"),
                html.Div(className="orbit-ring orbit-ring-2"),
                html.Div(className="orbit-ring orbit-ring-1"),
                html.Div(className="orbit-avatar", children=[
                    html.Div(html.Img(src="/assets/CENTRE_INTERET.png"), className="avatar-circle"),
                ]),
                *tags,
            ]),

            # Stats
            html.Div(className="stats-row", children=[
                html.Div(className="stat-card", children=[
                    html.Div(s["icon"], className="stat-icon"),
                    html.Div(s["value"], className="stat-value"),
                    html.Div(s["label"], className="stat-label"),
                ]) for s in stats_cards
            ]),

            # Detail panel
            html.Div(id="home-detail-panel", children=[]),
        ]),
        dcc.Store(id="home-selected-tag", data=None),
    ])

# ─── CALLBACKS ───────────────────────────────────────────────────────────────
@callback(
    Output("home-detail-panel", "children"),
    Input("home-selected-tag", "data"),
    prevent_initial_call=True,
)
def update_detail_panel(tag_id):
    if not tag_id:
        return []
    data     = load_interests()
    examples = data["examples"]
    is_kmeans = data.get("source") == "kmeans"
    
    # 1. Si on a cliqué sur une CATEGORIE (ex: "🎵 Musique")
    if tag_id in examples:
        cat     = tag_id
        ex_list = examples[cat]
        score   = data["scores"].get(cat, 0)
        
    # 2. Si on a cliqué sur un EXEMPLE / mot-clé
    else:
        parent_cat = next((c for c, exs in examples.items() if tag_id in exs), None)

        if parent_cat:
            cat = f"Sous-catégorie de {parent_cat}"
            if is_kmeans:
                score = data["scores"].get(parent_cat, 0)
            else:
                score = sum(1 for topic in data["raw_topics"] if tag_id.lower() in topic.lower())
            ex_list = [e for e in examples[parent_cat] if e != tag_id]
            ex_list.insert(0, tag_id)
        else:
            cat = tag_id
            ex_list = [tag_id]
            score = 0 if is_kmeans else sum(
                1 for topic in data["raw_topics"] if tag_id.lower() in topic.lower()
            )

    return html.Div(className="detail-panel", children=[
        html.Div(className="detail-panel-title", children=[
            cat,
            html.Span(f"  {score:,} occurrences",
                      style={"fontSize": "13px", "fontWeight": "400", "color": "var(--text-muted)"}),
        ]),
        html.Div(className="detail-chips", children=[
            html.Span(e, className="detail-chip") for e in ex_list
        ]),
        html.Div(
            "Sources : K-Means · YouTube · Google · Spotify · Netflix · Amazon"
            if is_kmeans else
            "Sources : Instagram Topics · X Personalization",
            className="detail-source"
        ),
    ])