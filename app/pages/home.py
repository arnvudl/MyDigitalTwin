import json
import math
import os
from functools import lru_cache

import pandas as pd
from dash import Input, Output, callback, html, dcc, ALL

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = r"C:\Users\arnau\Documents\MyDigitalTwin\warehouse"
IG_TOPICS_PATH = r"/data/raw/INSTAGRAM/preferences/your_topics/recommended_topics.json"
X_PERSONALIZATION_PATH = r"/data/raw/X/data/personalization.js"

CATEGORY_KEYWORDS = {
    "🎵 Musique":        ["music", "song", "artist", "rap", "album", "track", "beat", "drill", "trap", "afrobeat", "afropop", "rnb", "r&b", "hip", "hop"],
    "⚽ Sport":          ["foot", "football", "sport", "soccer", "nba", "league", "match", "goal", "player", "arsenal", "champions", "fifa", "ligue", "rugby", "tennis", "basketball"],
    "💻 Tech":           ["python", "code", "data", "dev", "javascript", "api", "ai", "software", "tech", "developer", "engineering", "science", "consumer tech"],
    "🎬 Cinéma/Séries":  ["netflix", "film", "série", "movie", "episode", "cinema", "watch", "trailer", "season", "tv", "show", "streaming"],
    "🎮 Gaming":         ["game", "gaming", "play", "xbox", "ps5", "steam", "minecraft", "fortnite", "esport", "gamer", "action game", "video game", "ar/vr"],
    "🌍 Actu/Société":   ["news", "actu", "society", "monde", "france", "afrique", "africa", "senegal", "politique", "cup of nations"],
    "🛍️ Shopping":       ["amazon", "shop", "product", "électronique", "brand", "adidas", "nike", "fashion", "style", "luxury"],
    "📸 Photo/Créa":     ["photo", "photography", "design", "creative", "art", "visual", "camera", "image", "graphic"],
}

# ─── DELTA READER ────────────────────────────────────────────────────────────
def _read_delta(table_name: str, cols: list) -> pd.DataFrame:
    table_path = os.path.join(DELTA_BASE, table_name)
    if not os.path.exists(table_path):
        return pd.DataFrame(columns=cols)
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
        except Exception:
            pass
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(columns=cols)

# ─── KEYWORDS ────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_all_keywords() -> dict:
    ig_topics, x_interests = [], []

    if os.path.exists(IG_TOPICS_PATH):
        with open(IG_TOPICS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("topics_your_topics", []):
            val = item.get("string_map_data", {}).get("Nom", {}).get("value", "")
            if val:
                ig_topics.append(val)

    if os.path.exists(X_PERSONALIZATION_PATH):
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

    all_topics = ig_topics + x_interests
    all_text   = " ".join(all_topics).lower()

    category_scores  = {}
    category_examples = {}

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(all_text.count(kw) for kw in keywords)
        category_scores[cat] = score
        found = []
        for topic in all_topics:
            if any(kw in topic.lower() for kw in keywords):
                clean = topic.strip()
                if clean not in found and len(clean) <= 30:
                    found.append(clean)
            if len(found) >= 10:
                break
        category_examples[cat] = found

    sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "scores":   {k: v for k, v in sorted_cats},
        "examples": category_examples,
    }

# ─── STATS ───────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def compute_stats() -> dict:
    stats = {}
    df = _read_delta("spotify_streams", ["artistName"])
    stats["artistes"] = df["artistName"].nunique() if not df.empty else 0
    df = _read_delta("netflix_views", ["show_title"])
    stats["films"] = len(df) if not df.empty else 0
    df = _read_delta("google_searches", ["query"])
    stats["recherches"] = len(df) if not df.empty else 0
    df = _read_delta("twitter_tweets", ["tweet_id"])
    stats["tweets"] = len(df) if not df.empty else 0
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
        tags.append(html.Div(
            id={"type": "orbit-tag", "index": f"ex-{i}"},
            className="orbit-tag tag-r2",
            style=style,
            children=[label],
            n_clicks=0,
        ))

    # ── Anneau 3 : catégories secondaires + exemples épars
    ring3_items = list(cats[6:])
    for cat in ring1[:3]:
        ring3_items += examples.get(cat, [])[2:4]

    for i, label in enumerate(ring3_items[:12]):
        angle = (360 / max(len(ring3_items), 1)) * i - 50
        style = _pos(angle, 340)
        tags.append(html.Div(
            id={"type": "orbit-tag", "index": f"ring3-{i}"},
            className="orbit-tag tag-r3",
            style=style,
            children=[label],
            n_clicks=0,
        ))

    return tags

# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    data  = load_all_keywords()
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
    data     = load_all_keywords()
    examples = data["examples"]
    if tag_id in examples:
        cat     = tag_id
        ex_list = examples[cat]
        score   = data["scores"].get(cat, 0)
    else:
        cat     = next((c for c, exs in examples.items() if tag_id in exs), tag_id)
        ex_list = examples.get(cat, [tag_id])
        score   = data["scores"].get(cat, 0)

    return html.Div(className="detail-panel", children=[
        html.Div(className="detail-panel-title", children=[
            cat,
            html.Span(f"  {score:,} occurrences",
                      style={"fontSize": "13px", "fontWeight": "400", "color": "var(--text-muted)"}),
        ]),
        html.Div(className="detail-chips", children=[
            html.Span(e, className="detail-chip") for e in ex_list
        ]),
        html.Div("Sources : Instagram Topics · X Personalization", className="detail-source"),
    ])