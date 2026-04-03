import math
import os
from functools import lru_cache

import pandas as pd
from dash import Input, Output, callback, html, dcc

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = "/opt/spark/warehouse"

CATEGORY_KEYWORDS = {
    "🎵 Musique": ["music", "song", "artist", "spotify", "rap", "album", "track",
                  "musique", "artiste", "chanson", "beat", "drill", "trap"],
    "⚽ Sport": ["foot", "football", "sport", "soccer", "nba", "league", "match",
                "goal", "player", "arsenal", "champions", "fifa", "ligue"],
    "💻 Tech": ["python", "code", "data", "dev", "javascript", "api", "ai",
               "machine learning", "software", "github", "dash", "spark",
               "big data", "streamlit", "programming", "tech", "developer"],
    "🎬 Cinéma/Séries": ["netflix", "film", "série", "movie", "episode", "cinema",
                        "mirror", "watch", "trailer", "season"],
    "🎮 Gaming": ["game", "gaming", "play", "xbox", "ps5", "steam", "minecraft",
                 "fortnite", "twitch", "esport", "gamer"],
    "🌍 Actu/Société": ["news", "actu", "politique", "society", "monde", "france",
                       "afrique", "twitter", "tweet", "senegal", "retweet"],
    "🛍️ Shopping": ["amazon", "order", "buy", "shop", "product", "électronique",
                    "cable", "price", "livraison"],
    "📱 Réseaux": ["instagram", "tiktok", "social", "post", "like", "reel",
                  "follow", "content", "creator", "influencer"],
}

# ─── DATA LOADING ─────────────────────────────────────────────────────────────
# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = r"C:\Users\arnau\Documents\MyDigitalTwin\warehouse"


def _read_delta(table_name: str, cols: list) -> pd.DataFrame:
    """Lit un dossier Delta Lake en Pandas (via les part-*.parquet)."""
    table_path = os.path.join(DELTA_BASE, table_name)
    if not os.path.exists(table_path):
        return pd.DataFrame(columns=cols)

    # Lire tous les fichiers parquet du dossier (ignorer _delta_log et .crc)
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
            # Garder seulement les colonnes demandées qui existent
            existing_cols = [c for c in cols if c in df.columns]
            if existing_cols:
                dfs.append(df[existing_cols])
        except Exception:
            pass

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(columns=cols)


# Stopwords à exclure
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "les", "des",
    "une", "est", "que", "dans", "pour", "sur", "avec", "par", "qui",
    "https", "http", "www", "com", "html", "php", "utm", "url", "null",
    "search", "query", "watch", "video", "youtube", "google", "tiktok",
    "instagram", "twitter", "spotify", "amazon", "apple", "content",
    "medium", "source", "term", "device", "creative", "match", "type",
    "mais", "fait", "faire", "j'ai", "like", "post", "posts", "plus",
    "dans", "avoir", "être", "tout", "bien", "aussi", "comme", "when",
    "what", "just", "your", "you", "not", "have", "about", "will",
    "they", "their", "can", "all", "new", "get", "its", "how",
    "very", "were", "been", "has", "had", "his", "her", "our",
}


def _is_clean_token(token: str) -> bool:
    """Retourne True si le token est lisible et utile."""
    token = token.strip()
    # Rejeter URLs
    if token.startswith("http") or "://" in token or "%" in token:
        return False
    # Rejeter les mentions @compte
    if token.startswith("@"):
        return False
    # Rejeter si se termine par ponctuation
    if token.endswith((".", ",", "!", "?")):
        return False
    # Rejeter trop court ou trop long
    if len(token) < 3 or len(token) > 40:
        return False
    # Rejeter stopwords
    if token.lower() in STOPWORDS:
        return False
    # Rejeter si contient des caractères parasites
    if any(c in token for c in ["=", "&", "?", "/", "\\", "%", "_", "{"]):
        return False
    return True


@lru_cache(maxsize=1)
def load_all_keywords() -> dict:
    """Charge les centres d'intérêt depuis les fichiers ads/topics des plateformes."""
    import json

    ig_path = r"C:\Users\arnau\Documents\MyDigitalTwin\data\raw\INSTAGRAM\preferences\your_topics\recommended_topics.json"
    x_path = r"C:\Users\arnau\Documents\MyDigitalTwin\data\raw\X\data\personalization.js"

    ig_topics = []
    x_interests = []

    # ── Instagram recommended_topics ─────────────────────────────────────────
    if os.path.exists(ig_path):
        with open(ig_path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("topics_your_topics", []):
            val = item.get("string_map_data", {}).get("Nom", {}).get("value", "")
            if val:
                ig_topics.append(val)

    # ── X personalization ─────────────────────────────────────────────────────
    if os.path.exists(x_path):
        with open(x_path, encoding="utf-8") as f:
            raw = f.read()
        if raw.strip().startswith("window."):
            raw = raw[raw.index("=") + 1:].strip()
        data = json.loads(raw)
        for entry in data:
            interests = (
                entry.get("p13nData", {})
                .get("interests", {})
                .get("interests", [])
            )
            for i in interests:
                name = i.get("name", "")
                if name and not i.get("isDisabled", False):
                    x_interests.append(name)

    # ── Combinaison + scoring par catégorie ──────────────────────────────────
    all_topics = ig_topics + x_interests
    all_text = " ".join(all_topics).lower()

    category_scores = {}
    category_examples = {}

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(all_text.count(kw) for kw in keywords)
        category_scores[cat] = score

        found = []
        for topic in all_topics:
            if any(kw in topic.lower() for kw in keywords):
                clean = topic.strip()
                if clean not in found and len(clean) <= 35:
                    found.append(clean)
            if len(found) >= 10:
                break
        category_examples[cat] = found

    sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)

    return {
        "scores": {k: v for k, v in sorted_cats},
        "examples": category_examples,
    }


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


# ─── TAG POSITIONING ──────────────────────────────────────────────────────────
def _polar_to_style(angle_deg: float, radius: float, center: float = 350) -> dict:
    """Convertit angle + rayon en style CSS (position absolute)."""
    rad = math.radians(angle_deg)
    x = center + radius * math.cos(rad)
    y = center + radius * math.sin(rad)
    return {
        "left": f"{x}px",
        "top": f"{y}px",
        "transform": "translate(-50%, -50%)",
    }


def build_orbit_tags(data: dict) -> list:
    """Construit tous les tags positionnés sur les 3 anneaux."""
    scores = data["scores"]
    examples = data["examples"]

    cats = list(scores.keys())
    tags = []

    # ── Anneau 1 : top 6 catégories ──────────────────────────────────────────
    ring1_cats = cats[:6]
    for i, cat in enumerate(ring1_cats):
        angle = (360 / len(ring1_cats)) * i - 90  # commence en haut
        style = _polar_to_style(angle, 130)
        tags.append(
            html.Div(
                id={"type": "orbit-tag", "index": cat},
                className="orbit-tag tag-ring-1",
                style=style,
                children=[
                    html.Span(className="tag-dot"),
                    cat,
                ],
                n_clicks=0,
            )
        )

    # ── Anneau 2 : top 3 exemples par catégorie (ring1 seulement) ────────────
    ring2_items = []
    for cat in ring1_cats[:4]:
        ex = examples.get(cat, [])[:2]
        for e in ex:
            ring2_items.append((e, cat))

    for i, (label, parent) in enumerate(ring2_items[:10]):
        angle = (360 / max(len(ring2_items), 1)) * i - 70
        style = _polar_to_style(angle, 215)
        tags.append(
            html.Div(
                id={"type": "orbit-tag", "index": f"ex-{i}"},
                className="orbit-tag tag-ring-2",
                style=style,
                children=[html.Span(className="tag-dot"), label],
                n_clicks=0,
            )
        )

    # ── Anneau 3 : catégories secondaires + exemples épars ───────────────────
    ring3_cats = cats[6:]
    ring3_items = [c for c in ring3_cats]
    for cat in ring1_cats[:3]:
        ex = examples.get(cat, [])[2:4]
        ring3_items += ex

    for i, label in enumerate(ring3_items[:12]):
        angle = (360 / max(len(ring3_items), 1)) * i - 50
        style = _polar_to_style(angle, 305)
        tags.append(
            html.Div(
                id={"type": "orbit-tag", "index": f"ring3-{i}"},
                className="orbit-tag tag-ring-3",
                style=style,
                children=[html.Span(className="tag-dot"), label],
                n_clicks=0,
            )
        )

    return tags


# ─── LAYOUT ───────────────────────────────────────────────────────────────────
def layout():
    data = load_all_keywords()
    stats = compute_stats()

    orbit_tags = build_orbit_tags(data)

    stats_cards = [
        {"icon": "🎵", "value": f"{stats['artistes']:,}", "label": "Artistes écoutés"},
        {"icon": "🎬", "value": f"{stats['films']:,}", "label": "Contenus Netflix"},
        {"icon": "🔍", "value": f"{stats['recherches']:,}", "label": "Recherches Google"},
        {"icon": "🐦", "value": f"{stats['tweets']:,}", "label": "Tweets postés"},
        {"icon": "📱", "value": str(len(data["scores"])), "label": "Centres d'intérêt"},
    ]

    return html.Div(
        className="page-wrapper",
        children=[
            # ── Hero ──────────────────────────────────────────────────────────
            html.Div(
                className="home-container",
                children=[
                    html.Div(
                        className="home-hero",
                        children=[
                            html.P("Données personnelles • 2022–2026", className="home-hero-label"),
                            html.H1(
                                html.Span(["My ", html.Em("Digital"), " Twin"]),
                                className="home-hero-title",
                            ),
                            html.P(
                                "Une radiographie de qui tu es, à travers tes données.",
                                className="home-hero-sub",
                            ),
                        ],
                    ),

                    # ── Orbit ─────────────────────────────────────────────────
                    html.Div(
                        className="orbit-section",
                        children=[
                            html.Div(className="orbit-ring orbit-ring-4"),
                            html.Div(className="orbit-ring orbit-ring-3"),
                            html.Div(className="orbit-ring orbit-ring-2"),
                            html.Div(className="orbit-ring orbit-ring-1"),
                            html.Div(
                                className="orbit-avatar",
                                children=[
                                    html.Div("🧠", className="avatar-circle"),
                                    html.Span("Arnau", className="avatar-name"),
                                ],
                            ),
                            *orbit_tags,
                        ],
                    ),

                    # ── Stats row ─────────────────────────────────────────────
                    html.Div(
                        className="stats-row",
                        children=[
                            html.Div(
                                className="stat-card",
                                children=[
                                    html.Div(s["icon"], className="stat-icon"),
                                    html.Div(s["value"], className="stat-value"),
                                    html.Div(s["label"], className="stat-label"),
                                ],
                            )
                            for s in stats_cards
                        ],
                    ),

                    # ── Detail panel (affiché au clic) ────────────────────────
                    html.Div(id="home-detail-panel", children=[]),
                ],
            ),

            # Store pour le tag sélectionné
            dcc.Store(id="home-selected-tag", data=None),
        ],
    )


# ─── CALLBACKS ────────────────────────────────────────────────────────────────
@callback(
    Output("home-detail-panel", "children"),
    Input("home-selected-tag", "data"),
    prevent_initial_call=True,
)
def update_detail_panel(tag_id):
    if not tag_id:
        return []

    data = load_all_keywords()
    examples = data["examples"]

    # tag_id peut être une catégorie ou un exemple
    if tag_id in examples:
        cat = tag_id
        ex_list = examples[cat]
        score = data["scores"].get(cat, 0)
    else:
        # cherche la catégorie parente
        cat = next((c for c, exs in examples.items() if tag_id in exs), tag_id)
        ex_list = examples.get(cat, [tag_id])
        score = data["scores"].get(cat, 0)

    chips = [html.Span(e, className="detail-chip") for e in ex_list]

    return html.Div(
        className="detail-panel",
        children=[
            html.Div(
                className="detail-panel-title",
                children=[cat, html.Span(f"  {score:,} occurrences", style={"fontSize": "13px", "fontWeight": "400",
                                                                            "color": "var(--text-muted)"})],
            ),
            html.Div(className="detail-chips", children=chips),
            html.Div(f"Sources : Google, YouTube, TikTok, Spotify, Instagram, Twitter, Amazon",
                     className="detail-source"),
        ],
    )
