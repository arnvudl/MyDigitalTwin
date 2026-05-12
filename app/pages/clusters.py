import os
import re
from functools import lru_cache

import pandas as pd
from dash import ALL, Input, Output, State, callback, dcc, html
import dash_mantine_components as dmc
from dash_iconify import DashIconify
from app.icons import svg_icon, PUZZLE
from config import APP_ASSETS_DIR, WAREHOUSE

# ─── FILTRE ANTI-PUB / BRUIT ─────────────────────────────────────────────────
# Patterns communs : campagnes YouTube (INH, VID 16x9), Chrome promos,
# pages de redirection Chrome, casino, ad blocker
_NOISE = re.compile(
    r'(?i)'
    r'\b\d{1,4}x\d{1,4}\b'           # Dimensions : 16x9, 1920x1080
    r'|\bINH\b'                        # Marqueur campagne YouTube
    r'|Choisissez Chrome|Kies Chrome|Choose Chrome'
    r'|^Redirect(?:ion)?[\.\s…]*$'   # Pages redirect Chrome
    r'|Ad Blocker'
    r'|VID\s+\d'
    r'|_[A-Z]{2}\b'                   # Suffixes campagne _FR, _BE
    r'|\bBoost_\d'
    r'|LinkedAccounts|FreeBankAccount'
    r'|\b\d+\s*sec\b'
    r'|casino'
    # Nouveaux patterns
    r'|^Shortened[:\s]'               # Google shortened ad URLs
    r'|[一-鿿぀-ヿ]' # Caractères chinois/japonais (pubs dans watch history)
    r'|\blening\b|\bkrediet\b'        # Pubs prêt bancaire néerlandais
    r'|CI/CD|TeamCity|JetBrains'      # Pubs outils dev
    r'|On the jobsite'                # DEWALT tagline
    r'|leaders aren'                  # idem
    r'|\bvolvo\b|\bDEWALT\b'         # Marques industrielles dans pubs YT
    r'|reconditionné.*Back\s*Mark'    # Pub Back Market
    r'|Enjoy a better'                # Pub SaaS générique
    r'|^Loading[\.…\s]*$'            # Pages en cours de chargement
    r'|lust\s+god'                   # Contenu adulte
    r'|Recherche\s+Google'           # Page résultat Google dans Chrome (doublon)
    r'|(\w+)\s+\1\.(com|net|org|be|fr|io)' # Titre = domaine répété : "nozgap nozgap.com"
)

def _clean_samples(samples: list) -> list:
    """Supprime les pubs, redirections et IDs de campagne des exemples."""
    cleaned = []
    for s in samples:
        if not s or not s.strip():
            continue
        if _NOISE.search(s):
            continue
        # Exclure les titres qui ressemblent à des IDs de campagne
        # (ex: "BNPPF_HY4 Boost_9x16_FR_12sec_2505")
        words = s.split()
        if words and re.match(r'^[A-Z0-9_]{5,}$', words[0]):
            continue
        cleaned.append(s)
    return cleaned

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = WAREHOUSE
ASSETS_DIR = APP_ASSETS_DIR

PLATFORM_COLORS = {
    "youtube":   ("#ff3b30", "rgba(255,59,48,0.18)",  "rgba(255,59,48,0.65)"),
    "spotify":   ("#1db954", "rgba(29,185,84,0.12)",  "rgba(29,185,84,0.6)"),
    "google":    ("#4285f4", "rgba(66,133,244,0.12)", "rgba(66,133,244,0.6)"),
    "netflix":   ("#e50914", "rgba(229,9,20,0.12)",   "rgba(229,9,20,0.6)"),
    "chrome":    ("#4285f4", "rgba(66,133,244,0.10)", "rgba(66,133,244,0.5)"),
    "tiktok":    ("#fe2c55", "rgba(254,44,85,0.12)",  "rgba(254,44,85,0.6)"),
    "instagram": ("#c13584", "rgba(193,53,132,0.12)", "rgba(193,53,132,0.6)"),
}
DEFAULT_COLOR = ("#888", "rgba(255,255,255,0.06)", "rgba(255,255,255,0.3)")


# ─── HELPERS ─────────────────────────────────────────────────────────────────
def _read_delta(table_name: str, cols: list) -> pd.DataFrame:
    table_path = os.path.join(DELTA_BASE, table_name)
    if not os.path.exists(table_path):
        return pd.DataFrame(columns=cols)

    # Respecter le log Delta : seuls les fichiers référencés par add/remove sont valides.
    log_dir = os.path.join(table_path, "_delta_log")
    if os.path.isdir(log_dir):
        import json as _json
        active, removed = set(), set()
        for fname in sorted(os.listdir(log_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(log_dir, fname)) as fh:
                for line in fh:
                    try:
                        entry = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    if "add" in entry and entry["add"]:
                        active.add(entry["add"]["path"])
                    if "remove" in entry and entry["remove"]:
                        removed.add(entry["remove"]["path"])
        active -= removed
        files = [os.path.join(table_path, p) for p in active]
    else:
        # Pas encore de Delta log — fallback Parquet brut (bootstrap)
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


def _to_list(val) -> list:
    """Convertit n'importe quelle valeur array-like (numpy, pyarrow, list, None) en list Python."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    try:
        return list(val)
    except Exception:
        return []


@lru_cache(maxsize=1)
def _read_profiles() -> pd.DataFrame:
    df = _read_delta("interest_profiles", [
        "cluster_id", "label", "emoji", "keywords",
        "top_platforms", "avg_hour", "time_period", "day_type",
        "item_count", "sample_items",
    ])
    if not df.empty:
        df = df.sort_values("cluster_id").reset_index(drop=True)
    return df


def _platform_color(platforms: list):
    if not platforms:
        return DEFAULT_COLOR
    return PLATFORM_COLORS.get(platforms[0], DEFAULT_COLOR)


def _fmt_hour(h: float) -> str:
    return f"{round(h):02d}h"


def _truncate(s: str, n: int = 48) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


# ─── CARD BUILDER ────────────────────────────────────────────────────────────
def _build_card(row: pd.Series, max_count: int, dimmed: bool = False) -> html.Div:
    label     = row.get("label", "Profil")
    emoji     = row.get("emoji", "")
    keywords  = _to_list(row.get("keywords"))
    platforms = _to_list(row.get("top_platforms"))
    samples   = _clean_samples(_to_list(row.get("sample_items")))
    avg_hour  = float(row.get("avg_hour",  0))
    time_per  = row.get("time_period", "")
    day_type  = row.get("day_type",    "")
    count     = int(row.get("item_count", 0))
    pct       = (count / max_count * 100) if max_count else 0

    accent, bg_tint, bar_fill = _platform_color(platforms)

    parts         = label.replace(emoji, "").strip().split("·")
    platform_part = parts[0].strip() if parts else label
    time_part     = parts[1].strip() if len(parts) > 1 else ""

    card_style = {
        "borderTopColor": accent,
        "background": f"linear-gradient(160deg, {bg_tint} 0%, rgba(28,28,30,0.4) 60%)",
        "opacity": "0.35" if dimmed else "1",
        "transition": "opacity 0.25s ease",
    }

    return html.Div(className="profile-card", style=card_style, children=[

        # ── Header ────────────────────────────────────────────────────────────
        html.Div(className="profile-card-header", children=[
            html.Span(emoji, className="profile-emoji"),
            html.Div(children=[
                html.Div(platform_part, className="profile-platform-name"),
                html.Div(time_part,     className="profile-time-name"),
            ]),
        ]),

        # ── Meta badges ───────────────────────────────────────────────────────
        dmc.Group(className="profile-meta", gap="xs", children=[
            dmc.Badge(time_per,            variant="light", size="sm", className="profile-meta-tag"),
            dmc.Badge(day_type,            variant="light", size="sm", className="profile-meta-tag"),
            dmc.Badge(_fmt_hour(avg_hour), variant="light", size="sm", className="profile-meta-tag"),
        ]),

        # ── Plateformes ───────────────────────────────────────────────────────
        dmc.Group(className="profile-platforms", gap="xs", children=[
            dmc.Badge(p.capitalize(), variant="outline", size="xs", className="profile-platform-chip",
                      style={"borderColor": accent, "color": accent})
            for p in platforms
        ]),

        # ── Exemples (items réels) ou keywords en fallback ────────────────────
        *([html.Div(className="profile-samples", children=[
            html.Div("Exemples", className="profile-section-label"),
            html.Ul(className="profile-sample-list", children=[
                html.Li(_truncate(s), className="profile-sample-item")
                for s in samples[:10]
            ]),
        ])] if samples else [html.Div(className="profile-samples", children=[
            html.Div("Mots-clés associés", className="profile-section-label"),
            html.Div(className="profile-keywords", children=[
                html.Span(kw, className="profile-keyword") for kw in keywords[:12]
            ]) if keywords else html.Div("—", className="profile-sample-empty"),
        ])]),

        # ── Keywords ──────────────────────────────────────────────────────────
        html.Details(className="profile-kw-details", children=[
            html.Summary("Mots-clés", className="profile-section-label profile-kw-toggle"),
            html.Div(className="profile-keywords", children=[
                html.Span(kw, className="profile-keyword")
                for kw in keywords
            ]),
        ]),

        # ── Barre de volume ───────────────────────────────────────────────────
        html.Div(children=[
            html.Div(className="profile-bar-track", children=[
                html.Div(className="profile-bar-fill",
                         style={"width": f"{pct:.1f}%", "background": bar_fill}),
            ]),
            html.Div(f"{count:,} items", className="profile-count"),
        ]),
    ])


# ─── CONTENT RENDERER (appelé au chargement + sur chaque filtre) ─────────────
def _render_content(active_filters: list, df: pd.DataFrame) -> list:
    """Retourne [filter-bar, viz-img?, grid]."""
    children = []

    if df.empty:
        return [html.P("Aucun profil à afficher.", style={"color": "var(--text-muted)"})]

    max_count = int(df["item_count"].max())

    # ── Collecte des valeurs disponibles pour les chips ────────────────────────
    all_platforms = []
    all_times     = []
    for _, row in df.iterrows():
        plats = _to_list(row.get("top_platforms"))
        for p in plats:
            if p not in all_platforms:
                all_platforms.append(p)
        t = row.get("time_period", "")
        if t and t not in all_times:
            all_times.append(t)

    def _chip(value, label=None, group="platform"):
        is_active = value in active_filters
        chip_id = {"type": "cluster-filter-chip", "index": f"{group}:{value}"}
        return html.Span(
            label or value.capitalize(),
            id=chip_id,
            className=f"filter-chip {'filter-chip-active' if is_active else ''}",
            n_clicks=0,
        )

    reset_chip = html.Span(
        "Tout",
        id={"type": "cluster-filter-chip", "index": "reset"},
        className=f"filter-chip filter-chip-reset {'filter-chip-active' if not active_filters else ''}",
        n_clicks=0,
    )

    filter_bar = html.Div(className="filter-bar", children=[
        html.Div("Plateforme", className="filter-label"),
        html.Div(className="filter-chips-row", children=[
            reset_chip,
            *[_chip(p, group="platform") for p in all_platforms],
        ]),
        html.Div("Moment", className="filter-label"),
        html.Div(className="filter-chips-row", children=[
            _chip(t, group="time") for t in all_times
        ]),
    ])
    children.append(filter_bar)

    # ── Viz image ─────────────────────────────────────────────────────────────
    if os.path.exists(os.path.join(ASSETS_DIR, "behavioral_profiles.png")):
        children.append(html.Div(className="clusters-viz", children=[
            html.Img(src="/assets/behavioral_profiles.png",
                     style={"width": "100%", "display": "block"}),
        ]))

    # ── Grille de cards ────────────────────────────────────────────────────────
    def _matches(row) -> bool:
        if not active_filters:
            return True
        plats = _to_list(row.get("top_platforms"))
        time  = row.get("time_period", "")
        for f in active_filters:
            if f in plats or f == time:
                return True
        return False

    cards = [
        _build_card(row, max_count, dimmed=not _matches(row))
        for _, row in df.iterrows()
    ]
    children.append(html.Div(className="clusters-grid", children=cards))

    return children


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    df = _read_profiles()

    if df.empty:
        return html.Div(className="page-wrapper", children=[
            html.Div(className="page-empty-state", children=[
                DashIconify(icon=PUZZLE, width=56, style={"color": "var(--text-secondary)"}),
                dmc.Title("Profils comportementaux", order=2),
                dmc.Text("Lance d'abord 03_fusion_visualization.ipynb.", c="dimmed", size="sm"),
            ])
        ])

    return html.Div(className="page-wrapper", children=[
        html.Div(className="clusters-container", children=[

            html.Div(className="home-hero", children=[
                dmc.Text("Analyse comportementale • 6 profils", className="home-hero-label"),
                dmc.Title(
                    html.Span(["Profils ", html.Em("Comportementaux")]),
                    order=1,
                    className="home-hero-title",
                    style={"fontSize": "56px"},
                ),
                dmc.Text(
                    "Comment, quand et sur quelle plateforme tu consommes du contenu.",
                    className="home-hero-sub",
                    c="dimmed",
                ),
            ]),

            dcc.Store(id="clusters-filter-store", data=[]),

            html.Div(
                id="clusters-content",
                children=_render_content([], df),
            ),
        ])
    ])


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
@callback(
    Output("clusters-filter-store", "data"),
    Input({"type": "cluster-filter-chip", "index": ALL}, "n_clicks"),
    State({"type": "cluster-filter-chip", "index": ALL}, "id"),
    State("clusters-filter-store", "data"),
    prevent_initial_call=True,
)
def toggle_filter(n_clicks_list, chip_ids, active_filters):
    from dash import ctx
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
        return active_filters

    raw = ctx.triggered_id.get("index", "")
    if raw == "reset":
        return []

    # raw = "platform:youtube" ou "time:Après-midi"
    value = raw.split(":", 1)[-1]

    active = list(active_filters or [])
    if value in active:
        active.remove(value)
    else:
        active.append(value)
    return active


@callback(
    Output("clusters-content", "children"),
    Input("clusters-filter-store", "data"),
)
def update_content(active_filters):
    df = _read_profiles()
    return _render_content(active_filters or [], df)
