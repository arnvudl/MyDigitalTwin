import json
import math
import os
import random
from functools import lru_cache
import re

import pandas as pd
from dash import Input, Output, callback, html, dcc, ALL
from app.icons import svg_icon, MUSIC, FILM, SEARCH, TWITTER, PHONE

# ─── CONFIG ──────────────────────────────────────────────────────────────────
# On vérifie si on est dans Docker (où les dossiers sont montés à la racine /app/data et /app/data/warehouse)
# ou en local (où les dossiers sont dans le répertoire courant).
if os.path.exists("/app/data/warehouse"):
    DELTA_BASE = "/app/data/warehouse"
    IG_TOPICS_PATH = "/app/data/raw/INSTAGRAM/preferences/your_topics/recommended_topics.json"
    X_PERSONALIZATION_PATH = "/app/data/raw/X/data/personalization.js"
else:
    DELTA_BASE = "data/warehouse"
    IG_TOPICS_PATH = "data/raw/INSTAGRAM/preferences/your_topics/recommended_topics.json"
    X_PERSONALIZATION_PATH = "data/raw/X/data/personalization.js"

CATEGORY_KEYWORDS = {
    "Sport": [
        "football", "soccer", "nba", "match", "goal", "player", "arsenal", "champions",
        "fifa", "ligue", "rugby", "tennis", "basketball", "sport", "ballon d'or", "ucl",
        "premier league", "ufc", "mma", "boxing", "gym", "fitness", "workout", "calisthenics",
        "training", "nfl", "olympics", "swimming", "cycling", "padel", "volleyball",
        "champions league", "ligue 1"
    ],
    "Auto/Moto": [
        "car", "auto", "voiture", "porsche", "ferrari", "lamborghini", "bmw", "mercedes",
        "audi", "tesla", "f1", "formula 1", "supercar", "hypercar", "drift", "tuning",
        "engine", "v8", "v12", "electric vehicle", "motorsport", "motorcycle", "moto",
        "yamaha", "kawasaki", "mclaren", "bugatti", "aston martin", "jdm", "nissan",
        "toyota", "supra", "rb26", "porsche 911", "rs6", "amg", "m performance", "ducati",
        "harley", "grand prix"
    ],
    "Musique": [
        "music", "song", "artist", "rap", "album", "track", "beat", "drill", "trap",
        "afrobeat", "afropop", "rnb", "r&b", "hip", "hop", "streaming", "spotify",
        "playlist", "concert", "festival", "lyrics", "producer", "instrumental", "pop",
        "rock", "techno", "house", "electro", "low fi", "lo-fi", "jazz", "synth", "dj",
        "remix", "type beat", "soundcloud", "rnboi", "l2b", "rema", "gazo", "freeze corleone",
        "niska", "ninho", "dimitri vegas", "damso", "tiakola", "zamdane", "bezbar",
        "travis scott", "bad bunny", "deejay", "frank ocean", "blaiz fayah", "mister v",
        "team bs", "sexion", "shatta", "bouyon", "soca", "gouyad", "zouk"
    ],
    "Tech": [
        "python", "code", "data", "dev", "javascript", "api", "ai", "software", "tech",
        "developer", "engineering", "science", "consumer tech", "technology", "equipment",
        "artificial intelligence", "machine learning", "deep learning", "nlp", "llm",
        "pytorch", "tensorflow", "backend", "frontend", "fullstack", "react", "github",
        "docker", "kubernetes", "cloud", "aws", "cybersecurity", "linux", "open source",
        "startup", "computer science", "rust", "typescript", "chatgpt", "openai", "gpu",
        "nvidia", "cuda", "mac"
    ],
    "Cinéma/Séries": [
        "netflix", "film", "série", "movie", "episode", "cinema", "watch", "trailer",
        "season", "tv", "show", "streaming", "anime", "manga", "crunchyroll", "hbo",
        "prime video", "disney+", "marvel", "dc comics", "star wars", "oscars",
        "documentary", "horror", "scifi", "animation", "otaku", "ghibli", "rick", "morty",
        "jojo's bizarre", "bojack horseman", "naruto", "shippuden", "fairy tail", "jojo",
        "baki", "boruto", "fullmetal", "one piece", "hunter", "demon slayer",
        "attack on titan", "fullmetal alchemist", "rick morty"
    ],
    "Gaming": [
        "game", "gaming", "play", "xbox", "ps5", "steam", "minecraft", "fortnite", "esport",
        "gamer", "action game", "video game", "ar/vr", "nintendo", "switch", "twitch",
        "discord", "multiplayer", "rpg", "fps", "roblox", "league of legends", "valorant",
        "warzone", "gta", "elden ring", "zelda", "playstation", "controller",
        "pc master race", "casino"
    ],
    "Actu/Société": [
        "news", "actu", "society", "monde", "france", "afrique", "africa", "senegal",
        "belgique", "politique", "cup of nations", "environment", "ecology", "climate",
        "space", "nasa", "spacex", "economy", "finance", "crypto", "bitcoin", "ethereum",
        "blockchain", "stock market", "history", "philosophy", "culture", "university"
    ],
    "Shopping": [
        "amazon", "shop", "product", "électronique", "brand", "adidas", "nike", "fashion",
        "streetwear", "sneakers", "yeezy", "jordan", "clothes", "outfit", "ecommerce",
        "unboxing", "skincare", "watches", "apple", "iphone", "samsung", "gadget",
        "deals", "dior", "louis vuitton", "stussy", "vintage", "airpods pro", "ralph lauren"
    ],
    "Photo/Créa": [
        "photo", "photography", "design", "creative", "art", "visual", "camera", "image",
        "graphic", "illustration", "photoshop", "lightroom", "editing", "video production",
        "content creation", "youtube", "tiktok", "reels", "architecture", "interior design",
        "digital art", "ui/ux", "portfolio", "3d modeling", "blender", "canva", "photopea"
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
    Charge les profils K-Means depuis data/warehouse/interest_profiles.
    Retourne None si le 01_exploration n'a pas encore tourné (fallback sur keyword matching).
    """
    df = _read_delta("interest_profiles", [
        "label", "emoji", "keywords", "top_platforms",
        "item_count", "time_period", "sample_items",
    ])
    if df.empty:
        return None

    scores, examples = {}, {}
    for _, row in df.iterrows():
        label   = row.get("label") or "Inconnu"
        def _to_list(val):
            if val is None: return []
            if isinstance(val, list): return val
            try: return list(val)
            except: return []
        kws     = _to_list(row.get("keywords"))
        samples = _to_list(row.get("sample_items"))
        count   = int(row.get("item_count") or 0)
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
def _kw_pattern(keywords: list) -> str:
    """Compile un pattern regex OR à partir d'une liste de keywords."""
    return '|'.join(r'(?<![a-z])' + re.escape(kw) + r'(?![a-z])' for kw in keywords)


def _delta_score(series: "pd.Series", pattern: str) -> int:
    """Compte combien de lignes d'une Series contiennent au moins un keyword."""
    if series is None or series.empty:
        return 0
    return int(series.str.contains(pattern, case=False, na=False, regex=True).sum())


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

    # ── Chargement des données Delta (scoring réel) ───────────────────────────
    df_google        = _read_delta("google_searches",    ["query"])
    df_youtube       = _read_delta("youtube_watch",      ["title"])
    df_chrome        = _read_delta("google_chrome",      ["title"])
    df_spotify       = _read_delta("spotify_streams",    ["artistName"])
    df_netflix       = _read_delta("netflix_views",      ["show_title"])
    df_tiktok_s      = _read_delta("tiktok_searches",    ["query"])
    df_ig_searches   = _read_delta("instagram_searches", ["query"])

    s_google       = df_google["query"]         if not df_google.empty       else None
    s_youtube      = df_youtube["title"]        if not df_youtube.empty      else None
    s_chrome       = df_chrome["title"]         if not df_chrome.empty       else None
    s_spotify      = df_spotify["artistName"]   if not df_spotify.empty      else None
    s_netflix      = df_netflix["show_title"]   if not df_netflix.empty      else None
    s_tiktok_s     = df_tiktok_s["query"]       if not df_tiktok_s.empty     else None
    s_ig_searches  = df_ig_searches["query"]    if not df_ig_searches.empty  else None

    category_scores   = {}
    category_examples = {}
    used_topics = set()

    for cat, keywords in CATEGORY_KEYWORDS.items():
        pattern = _kw_pattern(keywords)

        # ── Score topics (Instagram + X) ──────────────────────────────────────
        topic_score = 0
        found = []
        for topic in all_topics:
            topic_lower = topic.lower()
            if topic_lower in used_topics:
                continue
            is_match = False
            for kw in keywords:
                if topic_lower == kw:
                    is_match = True
                    break
                pat = r'(?:\b|_|-| )' + re.escape(kw) + r'(?:\b|_|-| )'
                if re.search(pat, topic_lower):
                    is_match = True
                    break
            if is_match:
                topic_score += 1
                clean = topic.strip()
                if clean not in found and len(clean) <= 35:
                    found.append(clean)
                used_topics.add(topic_lower)

        # ── Score Delta (données réelles) ─────────────────────────────────────
        delta_score = (
            _delta_score(s_google,      pattern) +
            _delta_score(s_youtube,     pattern) +
            _delta_score(s_chrome,      pattern) +
            _delta_score(s_spotify,     pattern) +
            _delta_score(s_netflix,     pattern) +
            _delta_score(s_tiktok_s,    pattern) +
            _delta_score(s_ig_searches, pattern)
        )

        category_scores[cat]   = topic_score + delta_score
        category_examples[cat] = found[:15]

    sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "scores":     {k: v for k, v in sorted_cats},
        "examples":   category_examples,
        "raw_topics": all_topics,
        "source":     "keywords",
    }


def load_interests() -> dict:
    """Toujours basé sur les données Delta Lake directement.
    Les résultats des notebooks sont affichés dans /profils."""
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

def build_orbit_tags(data: dict) -> list:
    scores   = data["scores"]
    examples = data["examples"]
    cats     = list(scores.keys())
    elements = []

    # Configuration des anneaux (rayon, durée de rotation, nombre d'astéroïdes)
    rings_config = [
        {"radius": 130, "duration": "35s", "items": cats[:6], "class": "tag-r1", "asteroids": 8},
        {"radius": 220, "duration": "50s", "items": [], "class": "tag-r2", "asteroids": 12}, # Rempli dynamiquement
        {"radius": 310, "duration": "70s", "items": [], "class": "tag-r3", "asteroids": 15}, # Rempli dynamiquement
        {"radius": 390, "duration": "90s", "items": [], "class": "tag-r3", "asteroids": 20}, # Décoratif
    ]

    # Remplissage de l'anneau 2 (exemples des top catégories)
    ring2_labels = []
    for cat in cats[:4]:
        ring2_labels.extend(examples.get(cat, [])[:2])
    rings_config[1]["items"] = ring2_labels[:10]

    # Remplissage de l'anneau 3 (catégories restantes + exemples)
    ring3_labels = cats[6:10]
    for cat in cats[:3]:
        ring3_labels.extend(examples.get(cat, [])[2:5])
    rings_config[2]["items"] = ring3_labels[:12]

    for config in rings_config:
        radius = config["radius"]
        duration = config["duration"]
        items = config.get("items", [])
        
        # Ajouter les étiquettes (Tags)
        for i, label in enumerate(items):
            angle = (360 / max(len(items), 1)) * i
            
            # Plus besoin du wrapper statique externe, on gère tout via les variables CSS
            elements.append(html.Div(
                className="orbit-wrapper gravitate",
                style={
                    "--duration": duration,
                    "--start-angle": f"{angle}deg"
                },
                children=[
                    html.Div(
                        id={"type": "orbit-tag", "index": label},
                        className=f"orbit-tag {config['class']}",
                        style={"left": f"{radius}px"},
                        children=[label],
                        n_clicks=0,
                    )
                ]
            ))

        # Ajouter des astéroïdes décoratifs
        for i in range(config.get("asteroids", 0)):
            ast_angle = random.uniform(0, 360)
            ast_offset = random.uniform(-10, 10)
            ast_duration = f"{float(duration[:-1]) * random.uniform(0.8, 1.2):.1f}s"
            
            elements.append(html.Div(
                className="orbit-wrapper gravitate",
                style={
                    "--duration": ast_duration,
                    "--start-angle": f"{ast_angle}deg"
                },
                children=[
                    html.Div(
                        className="asteroid",
                        style={
                            "left": f"{radius + ast_offset}px",
                            "opacity": random.uniform(0.2, 0.6)
                        }
                    )
                ]
            ))

    return elements

# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    data  = load_interests()
    stats = compute_stats()
    random.seed(42) # Pour garder la même disposition au rafraîchissement
    tags  = build_orbit_tags(data)

    stats_cards = [
        {"icon": svg_icon(MUSIC),   "value": f"{stats['artistes']:,}", "label": "Artistes écoutés"},
        {"icon": svg_icon(FILM),    "value": f"{stats['films']:,}",    "label": "Contenus Netflix"},
        {"icon": svg_icon(SEARCH),  "value": f"{stats['recherches']:,}", "label": "Recherches Google"},
        {"icon": svg_icon(TWITTER), "value": f"{stats['tweets']:,}",   "label": "Tweets postés"},
        {"icon": svg_icon(PHONE),   "value": str(len(data["scores"])), "label": "Centres d'intérêt"},
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
    
    # 1. Si on a cliqué sur une CATEGORIE (ex: "Musique")
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
            "Sources : K-Means · YouTube · Google · Spotify · Netflix"
            if is_kmeans else
            "Sources : Instagram Topics · X Personalization",
            className="detail-source"
        ),
    ])