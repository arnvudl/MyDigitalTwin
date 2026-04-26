from dash import html, dcc

# ─── DATA LINEAGE ─────────────────────────────────────────────────────────────
# Statuts : "full" = ingéré + page dashboard | "ingested" = ingéré, pas de page
#           "partial" = utilisé indirectement / partiellement | "missing" = pas ingéré

PLATFORMS = [
    {
        "name": "Instagram",
        "emoji": "📸",
        "color": "#e1306c",
        "bg": "#fff0f5",
        "sources": [
            {"name": "liked_posts.json",           "status": "full",      "pages": ["Timeline", "Profils"],   "note": ""},
            {"name": "saved_posts.json",            "status": "full",      "pages": ["Timeline", "Profils"],   "note": ""},
            {"name": "post_comments_*.json",        "status": "full",      "pages": ["Timeline", "Profils"],   "note": ""},
            {"name": "messages/inbox/ (DMs)",       "status": "full",      "pages": ["Social"],                "note": "graphe social"},
            {"name": "recommended_topics.json",     "status": "partial",   "pages": ["Home"],                  "note": "fichier raw, pas warehouse"},
            {"name": "story_likes.json",            "status": "full",      "pages": ["Timeline", "Profils"],   "note": ""},
            {"name": "posts_viewed.json",           "status": "full",      "pages": ["Timeline", "Profils"],   "note": ""},
            {"name": "videos_watched.json",         "status": "full",      "pages": ["Timeline", "Profils"],   "note": ""},
            {"name": "ads_clicked/viewed.json",     "status": "missing",   "pages": [],                        "note": "non ingéré"},
            {"name": "word_or_phrase_searches.json","status": "full",      "pages": ["Timeline", "Home", "Profils"], "note": ""},
            {"name": "locations_of_interest.json",  "status": "missing",   "pages": [],                        "note": "non ingéré"},
        ],
    },
    {
        "name": "TikTok",
        "emoji": "🎵",
        "color": "#374151",
        "bg": "#f8f8f8",
        "sources": [
            {"name": "VideoHistory",                "status": "full",      "pages": ["Timeline"],              "note": ""},
            {"name": "LikeHistory",                 "status": "full",      "pages": ["Timeline", "Profils"],   "note": ""},
            {"name": "SearchHistory",               "status": "full",      "pages": ["Timeline", "Home", "Profils"], "note": ""},
            {"name": "Comment",                     "status": "ingested",  "pages": [],                        "note": "ingéré, non visualisé"},
            {"name": "DirectMessages (texte)",      "status": "full",      "pages": ["Analyse (psy)"],         "note": ""},
            {"name": "DirectMessages (meta)",       "status": "ingested",  "pages": [],                        "note": "ingéré, non visualisé"},
            {"name": "FavoriteHashtags",            "status": "ingested",  "pages": [],                        "note": "ingéré, non visualisé"},
            {"name": "AdsInterests",                "status": "ingested",  "pages": [],                        "note": "ingéré, non visualisé"},
        ],
    },
    {
        "name": "Spotify",
        "emoji": "🎧",
        "color": "#1db954",
        "bg": "#f0fdf4",
        "sources": [
            {"name": "StreamingHistory_music_*.json","status": "full",     "pages": ["Spotify", "Timeline", "Recommandations"], "note": ""},
            {"name": "YourLibrary.json",            "status": "full",      "pages": ["Recommandations"],       "note": ""},
            {"name": "Playlist1.json",              "status": "full",      "pages": ["Spotify"],               "note": ""},
            {"name": "YourSoundCapsule.json",       "status": "full",      "pages": ["Spotify"],               "note": ""},
        ],
    },
    {
        "name": "Netflix",
        "emoji": "🎬",
        "color": "#e50914",
        "bg": "#fff5f5",
        "sources": [
            {"name": "NetflixViewingHistory.csv",   "status": "full",      "pages": ["Netflix", "Timeline", "Recommandations"], "note": ""},
        ],
    },
    {
        "name": "Google / YouTube",
        "emoji": "🔍",
        "color": "#4285f4",
        "bg": "#eff6ff",
        "sources": [
            {"name": "Recherche/MonActivité.html",  "status": "full",      "pages": ["Home", "Profils", "Timeline"], "note": ""},
            {"name": "Chrome/MonActivité.html",     "status": "full",      "pages": ["Home", "Profils"],        "note": ""},
            {"name": "YouTube watch-history.html",  "status": "full",      "pages": ["Home", "Profils", "Timeline"], "note": ""},
            {"name": "YouTube search history",      "status": "full",      "pages": ["Home", "Profils"],        "note": ""},
            {"name": "Maps/MonActivité.html",       "status": "missing",   "pages": [],                        "note": "non ingéré"},
            {"name": "Discover/MonActivité.html",   "status": "missing",   "pages": [],                        "note": "non ingéré"},
            {"name": "Vols / Voyages / Hôtels",     "status": "missing",   "pages": [],                        "note": "non ingéré"},
            {"name": "Adresses enregistrées.json",  "status": "missing",   "pages": [],                        "note": "non ingéré"},
        ],
    },
    {
        "name": "Twitter / X",
        "emoji": "🐦",
        "color": "#1d9bf0",
        "bg": "#f0f9ff",
        "sources": [
            {"name": "tweets.js",                   "status": "full",      "pages": ["Timeline", "Profils"],   "note": ""},
            {"name": "like.js",                     "status": "ingested",  "pages": [],                        "note": "ingéré, non visualisé"},
            {"name": "saved-search.js",             "status": "ingested",  "pages": [],                        "note": "ingéré, non visualisé"},
        ],
    },
    {
        "name": "Apple",
        "emoji": "🍎",
        "color": "#6b7280",
        "bg": "#f9fafb",
        "sources": [
            {"name": "App Install Activity.csv",    "status": "ingested",  "pages": [],                        "note": "ingéré, non visualisé"},
            {"name": "Apps Using Sign In with Apple.csv", "status": "ingested", "pages": [],                   "note": "ingéré, non visualisé"},
        ],
    },
]

STATUS_CONFIG = {
    "full":     {"label": "Visualisé",    "color": "#15803d", "bg": "#dcfce7"},
    "partial":  {"label": "Partiel",      "color": "#92400e", "bg": "#fef3c7"},
    "ingested": {"label": "Ingéré",       "color": "#1d4ed8", "bg": "#dbeafe"},
    "missing":  {"label": "Non ingéré",   "color": "#9f1239", "bg": "#ffe4e6"},
}

# ─── STATS ────────────────────────────────────────────────────────────────────
def _compute_stats():
    total = sum(len(p["sources"]) for p in PLATFORMS)
    full = sum(1 for p in PLATFORMS for s in p["sources"] if s["status"] == "full")
    ingested = sum(1 for p in PLATFORMS for s in p["sources"] if s["status"] == "ingested")
    partial = sum(1 for p in PLATFORMS for s in p["sources"] if s["status"] == "partial")
    missing = sum(1 for p in PLATFORMS for s in p["sources"] if s["status"] == "missing")
    return total, full, ingested, partial, missing


# ─── LAYOUT ───────────────────────────────────────────────────────────────────
def layout():
    total, full, ingested, partial, missing = _compute_stats()

    stat_cards = html.Div(
        style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)", "gap": "0.75rem", "marginBottom": "2rem"},
        children=[
            _stat_card(str(full),     "Visualisés",  "#dcfce7", "#15803d"),
            _stat_card(str(ingested), "Ingérés seulement", "#dbeafe", "#1d4ed8"),
            _stat_card(str(partial),  "Partiels",    "#fef3c7", "#92400e"),
            _stat_card(str(missing),  "Non ingérés", "#ffe4e6", "#9f1239"),
        ]
    )

    platform_blocks = [_platform_block(p) for p in PLATFORMS]

    return html.Div(
        style={"padding": "2rem", "maxWidth": "1100px", "margin": "0 auto", "fontFamily": "var(--font, Inter, sans-serif)"},
        children=[
            html.Div(
                style={"marginBottom": "1.5rem"},
                children=[
                    html.H1("Inventaire des données", style={"fontSize": "1.4rem", "fontWeight": "600", "marginBottom": "0.25rem"}),
                    html.P(
                        f"{total} sources · {full} visualisées · {missing} non ingérées",
                        style={"color": "var(--text-muted, #64748b)", "fontSize": "0.9rem"}
                    ),
                ]
            ),
            stat_cards,
            html.Div(children=platform_blocks),
        ]
    )


def _stat_card(number, label, bg, fg):
    return html.Div(
        style={"background": bg, "borderRadius": "10px", "padding": "1rem 1.25rem"},
        children=[
            html.Div(number, style={"fontSize": "2rem", "fontWeight": "700", "color": fg, "lineHeight": "1"}),
            html.Div(label,  style={"fontSize": "0.78rem", "fontWeight": "500", "color": fg, "marginTop": "4px", "opacity": "0.85"}),
        ]
    )


def _platform_block(platform):
    rows = []
    for src in platform["sources"]:
        cfg = STATUS_CONFIG[src["status"]]
        badge = html.Span(
            cfg["label"],
            style={
                "fontSize": "0.7rem", "fontWeight": "600",
                "padding": "2px 8px", "borderRadius": "999px",
                "background": cfg["bg"], "color": cfg["color"],
                "whiteSpace": "nowrap",
            }
        )

        pages_chips = html.Div(
            style={"display": "flex", "gap": "4px", "flexWrap": "wrap"},
            children=[
                html.Span(
                    p,
                    style={
                        "fontSize": "0.68rem", "padding": "2px 7px", "borderRadius": "999px",
                        "background": "#f1f5f9", "color": "#475569", "fontWeight": "500",
                    }
                )
                for p in src["pages"]
            ] or [html.Span("—", style={"color": "#cbd5e1", "fontSize": "0.75rem"})]
        )

        rows.append(
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 120px 1fr",
                    "alignItems": "center",
                    "gap": "1rem",
                    "padding": "0.6rem 0",
                    "borderBottom": "1px solid #f1f5f9",
                },
                children=[
                    html.Span(src["name"], style={"fontSize": "0.82rem", "fontFamily": "monospace", "color": "#334155"}),
                    badge,
                    pages_chips,
                ]
            )
        )

    return html.Div(
        style={
            "background": "#fff",
            "border": "1px solid #e4e8ef",
            "borderRadius": "12px",
            "padding": "1.25rem 1.5rem",
            "marginBottom": "1rem",
            "borderLeft": f"4px solid {platform['color']}",
        },
        children=[
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "0.6rem", "marginBottom": "0.75rem"},
                children=[
                    html.Span(platform["emoji"], style={"fontSize": "1.2rem"}),
                    html.Span(platform["name"], style={"fontWeight": "600", "fontSize": "1rem"}),
                ]
            ),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 120px 1fr", "gap": "1rem", "marginBottom": "0.5rem"},
                children=[
                    html.Span("Source", style={"fontSize": "0.7rem", "fontWeight": "600", "color": "#94a3b8", "textTransform": "uppercase", "letterSpacing": "0.05em"}),
                    html.Span("Statut",  style={"fontSize": "0.7rem", "fontWeight": "600", "color": "#94a3b8", "textTransform": "uppercase", "letterSpacing": "0.05em"}),
                    html.Span("Pages",   style={"fontSize": "0.7rem", "fontWeight": "600", "color": "#94a3b8", "textTransform": "uppercase", "letterSpacing": "0.05em"}),
                ]
            ),
            html.Div(children=rows),
        ]
    )
