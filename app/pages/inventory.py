import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify

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
    "full":     {"label": "Visualisé",    "dmc_color": "green"},
    "partial":  {"label": "Partiel",      "dmc_color": "yellow"},
    "ingested": {"label": "Ingéré",       "dmc_color": "blue"},
    "missing":  {"label": "Non ingéré",   "dmc_color": "red"},
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

    stat_cards = dmc.SimpleGrid(
        cols=4,
        spacing="md",
        style={"marginBottom": "2rem"},
        children=[
            _stat_card(str(full),     "Visualisés",       "green"),
            _stat_card(str(ingested), "Ingérés seulement","blue"),
            _stat_card(str(partial),  "Partiels",         "yellow"),
            _stat_card(str(missing),  "Non ingérés",      "red"),
        ]
    )

    platform_blocks = [_platform_block(p) for p in PLATFORMS]

    return html.Div(
        className="page-wrapper",
        children=[
            html.Div(
                style={"padding": "2rem", "maxWidth": "1100px", "margin": "0 auto"},
                children=[
                    dmc.Stack(gap="xs", mb="lg", children=[
                        dmc.Group(children=[
                            DashIconify(icon="tabler:package", width=24),
                            dmc.Title("Inventaire des données", order=1,
                                      style={"fontSize": "1.4rem", "fontWeight": "600"}),
                        ]),
                        dmc.Text(
                            f"{total} sources · {full} visualisées · {missing} non ingérées",
                            size="sm", c="dimmed",
                        ),
                    ]),
                    stat_cards,
                    dmc.Stack(gap="md", children=platform_blocks),
                ]
            ),
        ]
    )


def _stat_card(number, label, color):
    return dmc.Card(
        withBorder=True,
        radius="md",
        p="md",
        children=[
            dmc.Text(number, size="xl", fw=700, c=color, style={"fontSize": "2rem", "lineHeight": "1"}),
            dmc.Text(label, size="xs", fw=500, c="dimmed", mt=4),
        ]
    )


def _platform_block(platform):
    rows = []
    for src in platform["sources"]:
        cfg = STATUS_CONFIG[src["status"]]
        badge = dmc.Badge(
            cfg["label"],
            color=cfg["dmc_color"],
            variant="light",
            size="sm",
            radius="xl",
        )

        pages_chips = dmc.Group(
            gap=4,
            wrap="wrap",
            children=[
                dmc.Badge(p, variant="outline", size="xs", radius="xl", color="gray")
                for p in src["pages"]
            ] or [dmc.Text("—", size="xs", c="dimmed")],
        )

        rows.append(
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 120px 1fr",
                    "alignItems": "center",
                    "gap": "1rem",
                    "padding": "0.6rem 0",
                    "borderBottom": "1px solid rgba(255,255,255,0.06)",
                },
                children=[
                    dmc.Text(src["name"], size="sm", style={"fontFamily": "monospace"}),
                    badge,
                    pages_chips,
                ]
            )
        )

    return dmc.Card(
        withBorder=True,
        radius="md",
        p="lg",
        style={"borderLeft": f"4px solid {platform['color']}"},
        children=[
            dmc.Group(mb="md", children=[
                html.Span(platform["emoji"], style={"fontSize": "1.2rem"}),
                dmc.Text(platform["name"], fw=600, size="md"),
            ]),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 120px 1fr", "gap": "1rem", "marginBottom": "0.5rem"},
                children=[
                    dmc.Text("Source", size="xs", fw=600, c="dimmed", tt="uppercase"),
                    dmc.Text("Statut", size="xs", fw=600, c="dimmed", tt="uppercase"),
                    dmc.Text("Pages",  size="xs", fw=600, c="dimmed", tt="uppercase"),
                ]
            ),
            html.Div(children=rows),
        ]
    )
