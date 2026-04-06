import os
import re
import pandas as pd
from difflib import SequenceMatcher
from dash import Input, Output, State, callback, clientside_callback, dcc, html, no_update

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = "/app/warehouse" if os.path.exists("/app/warehouse") else "warehouse"

PLATFORM_CFG = {
    "netflix": {
        "color":  "#e50914",
        "dim":    "rgba(229,9,20,0.15)",
        "bar":    "rgba(229,9,20,0.8)",
        "emoji":  "🎬",
        "label":  "Netflix",
        "noun":   "film / série",
        "verb":   "regardé",
        "placeholder": "ex: Breaking Bad, Interstellar…",
    },
    "spotify": {
        "color":  "#1db954",
        "dim":    "rgba(29,185,84,0.15)",
        "bar":    "rgba(29,185,84,0.8)",
        "emoji":  "🎵",
        "label":  "Spotify",
        "noun":   "titre / artiste",
        "verb":   "écouté",
        "placeholder": "ex: Naruto — Silhouette, Drake…",
    },
}


# ─── DATA ────────────────────────────────────────────────────────────────────
def _load_scores() -> pd.DataFrame:
    path = os.path.join(DELTA_BASE, "als_scores")
    if not os.path.exists(path):
        return pd.DataFrame()
    files = [
        os.path.join(path, f)
        for f in os.listdir(path)
        if f.endswith(".parquet") and not f.startswith(".")
    ]
    if not files:
        return pd.DataFrame()
    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    df["item_title_lower"] = df["item_title"].str.lower().str.strip()
    return df


# ─── FUZZY SEARCH ────────────────────────────────────────────────────────────
def _find_match(query: str, platform: str, df: pd.DataFrame):
    """Retourne (row, ratio) du meilleur match, ou (None, 0)."""
    if df.empty or not query.strip():
        return None, 0

    q = query.lower().strip()
    sub = df[df["platform"] == platform] if platform else df

    if sub.empty:
        return None, 0

    # 1. Correspondance exacte
    exact = sub[sub["item_title_lower"] == q]
    if not exact.empty:
        return exact.iloc[0], 1.0

    # 2. Correspondance partielle (q contenu dans le titre ou vice-versa)
    partial = sub[
        sub["item_title_lower"].str.contains(re.escape(q), regex=True, na=False) |
        sub["item_title_lower"].apply(lambda t: q in t)
    ]
    if not partial.empty:
        best = partial.loc[partial["predicted_score"].idxmax()]
        return best, 0.9

    # 3. Fuzzy matching (SequenceMatcher) sur un sous-ensemble pré-filtré
    words = [w for w in q.split() if len(w) > 2]
    if words:
        pattern = "|".join(re.escape(w) for w in words)
        candidates = sub[sub["item_title_lower"].str.contains(pattern, regex=True, na=False)]
    else:
        candidates = sub

    if candidates.empty:
        candidates = sub

    best_ratio, best_row = 0.0, None
    for _, row in candidates.iterrows():
        ratio = SequenceMatcher(None, q, row["item_title_lower"]).ratio()
        if ratio > best_ratio:
            best_ratio, best_row = ratio, row

    if best_ratio >= 0.55:
        return best_row, best_ratio
    return None, 0


def _similar_items(found_title: str, score: float, platform: str, df: pd.DataFrame, n: int = 6):
    """Items similaires : même plateforme, déjà consommés, score proche."""
    if df.empty:
        return []
    sub = df[
        (df["platform"] == platform) &
        (df["item_title"] != found_title)
    ].copy()
    sub["score_diff"] = (sub["predicted_score"] - score).abs()
    sub = sub.sort_values("score_diff").head(n)
    return sub.to_dict("records")


# ─── SCORE COLOR ─────────────────────────────────────────────────────────────
def _score_color(score: float) -> str:
    if score >= 80: return "#30d158"
    if score >= 60: return "#ffd60a"
    if score >= 40: return "#ff9f0a"
    return "#ff453a"


def _score_label(score: float) -> str:
    if score >= 85: return "Arnaud adorera"
    if score >= 70: return "Arnaud aimera probablement"
    if score >= 50: return "Arnaud pourrait aimer"
    if score >= 30: return "Arnaud aimera peu"
    return "Arnaud n'aimera probablement pas"


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    return html.Div(className="page-wrapper", children=[
        html.Div(
            style={"maxWidth": "860px", "margin": "0 auto", "padding": "40px 32px 80px"},
            children=[

                # ── Hero ──────────────────────────────────────────────────────
                html.Div(className="home-hero", style={"marginBottom": "48px"}, children=[
                    html.P("ALS · Similarité · Score d'affinité", className="home-hero-label"),
                    html.H1(
                        html.Span(["Mes ", html.Em("Recommandations")]),
                        className="home-hero-title",
                        style={"fontSize": "56px"},
                    ),
                    html.P(
                        "Tape un titre de film ou de musique pour savoir à quel point tu l'aimeras.",
                        className="home-hero-sub",
                    ),
                ]),

                # ── Sélecteur de plateforme ────────────────────────────────────
                html.Div(style={"display": "flex", "gap": "10px", "marginBottom": "20px",
                                "justifyContent": "center"},
                         children=[
                    html.Button(
                        "🎬  Netflix",
                        id="reco-btn-netflix",
                        n_clicks=0,
                        style=_toggle_btn_style("#e50914", active=True),
                    ),
                    html.Button(
                        "🎵  Spotify",
                        id="reco-btn-spotify",
                        n_clicks=0,
                        style=_toggle_btn_style("#1db954", active=False),
                    ),
                ]),

                # ── Store plateforme active ────────────────────────────────────
                dcc.Store(id="reco-platform", data="netflix"),

                # ── Champ de recherche ────────────────────────────────────────
                html.Div(style={"display": "flex", "gap": "10px", "marginBottom": "40px"},
                         children=[
                    dcc.Input(
                        id="reco-input",
                        type="text",
                        placeholder="ex: Breaking Bad, Interstellar…",
                        debounce=False,
                        n_submit=0,
                        style={
                            "flex": "1",
                            "background": "rgba(28,28,30,0.7)",
                            "border": "1px solid rgba(255,255,255,0.12)",
                            "borderRadius": "12px",
                            "padding": "14px 20px",
                            "fontSize": "16px",
                            "color": "#fff",
                            "outline": "none",
                            "fontFamily": "var(--font-family)",
                        },
                    ),
                    html.Button(
                        "Rechercher →",
                        id="reco-search-btn",
                        n_clicks=0,
                        style={
                            "background": "#e50914",
                            "color": "#fff",
                            "border": "none",
                            "borderRadius": "12px",
                            "padding": "14px 24px",
                            "fontSize": "14px",
                            "fontWeight": "600",
                            "cursor": "pointer",
                            "fontFamily": "var(--font-family)",
                            "whiteSpace": "nowrap",
                        },
                    ),
                ]),

                # ── Stores animation ──────────────────────────────────────────
                dcc.Store(id="reco-result-store", data={}),
                dcc.Store(id="reco-anim-store",   data={"target": 0, "current": 0}),
                dcc.Interval(id="reco-anim-interval", interval=25, n_intervals=0, disabled=True),

                # ── Zone de résultat ──────────────────────────────────────────
                html.Div(id="reco-result-area"),
            ],
        )
    ])


def _toggle_btn_style(color: str, active: bool) -> dict:
    return {
        "background": color if active else "rgba(28,28,30,0.6)",
        "color":  "#fff",
        "border": f"1px solid {color}",
        "borderRadius": "100px",
        "padding": "10px 24px",
        "fontSize": "14px",
        "fontWeight": "600",
        "cursor": "pointer",
        "fontFamily": "var(--font-family)",
        "transition": "all 0.2s ease",
        "opacity": "1" if active else "0.55",
    }


# ─── CALLBACKS ───────────────────────────────────────────────────────────────

# Mise à jour du style des boutons + placeholder input
@callback(
    Output("reco-platform", "data"),
    Output("reco-btn-netflix", "style"),
    Output("reco-btn-spotify", "style"),
    Output("reco-input", "placeholder"),
    Output("reco-search-btn", "style"),
    Input("reco-btn-netflix", "n_clicks"),
    Input("reco-btn-spotify", "n_clicks"),
    State("reco-platform", "data"),
    prevent_initial_call=True,
)
def switch_platform(nc_netflix, nc_spotify, current):
    from dash import ctx
    triggered = ctx.triggered_id
    if triggered == "reco-btn-netflix":
        plat = "netflix"
    elif triggered == "reco-btn-spotify":
        plat = "spotify"
    else:
        plat = current or "netflix"

    cfg   = PLATFORM_CFG[plat]
    color = cfg["color"]
    btn_style = {
        "background": color, "color": "#fff", "border": "none",
        "borderRadius": "12px", "padding": "14px 24px",
        "fontSize": "14px", "fontWeight": "600", "cursor": "pointer",
        "fontFamily": "var(--font-family)", "whiteSpace": "nowrap",
    }
    return (
        plat,
        _toggle_btn_style("#e50914", plat == "netflix"),
        _toggle_btn_style("#1db954", plat == "spotify"),
        cfg["placeholder"],
        btn_style,
    )


# Recherche → résultat + démarrage animation
@callback(
    Output("reco-result-store",  "data"),
    Output("reco-anim-store",    "data",     allow_duplicate=True),
    Output("reco-anim-interval", "disabled", allow_duplicate=True),
    Output("reco-anim-interval", "n_intervals"),
    Input("reco-search-btn", "n_clicks"),
    Input("reco-input", "n_submit"),
    State("reco-input", "value"),
    State("reco-platform", "data"),
    prevent_initial_call=True,
)
def do_search(n_clicks, n_submit, query, platform):
    if not query or not query.strip():
        return no_update, no_update, True, no_update

    platform = platform or "netflix"
    df = _load_scores()

    row, ratio = _find_match(query, platform, df)

    if row is not None:
        score   = float(row["predicted_score"])
        title   = row["item_title"]
        plays   = int(row.get("play_count", 0))
        similar = _similar_items(title, score, platform, df, n=6)
        result  = {
            "found":    True,
            "title":    title,
            "query":    query.strip(),
            "score":    score,
            "plays":    plays,
            "ratio":    round(ratio, 2),
            "platform": platform,
            "similar":  similar,
        }
    else:
        # Pas trouvé : top suggestions de la plateforme
        top = df[df["platform"] == platform].sort_values("predicted_score", ascending=False).head(6)
        result = {
            "found":     False,
            "query":     query.strip(),
            "platform":  platform,
            "top_items": top.to_dict("records"),
        }

    anim = {"target": int(result.get("score", 0)), "current": 0}
    return result, anim, False, 0  # démarre l'interval


# Animation du compteur (clientside → pas de round-trip serveur)
clientside_callback(
    """
    function(n, store) {
        if (!store || store.target === 0) {
            return [window.dash_clientside.no_update, store, true];
        }
        var current = store.current || 0;
        var target  = store.target  || 0;
        if (current >= target) {
            return [target + "%", store, true];
        }
        var step = Math.max(1, Math.ceil((target - current) / 12));
        var next = Math.min(current + step, target);
        return [next + "%", {target: target, current: next}, next >= target];
    }
    """,
    Output("reco-score-counter", "children"),
    Output("reco-anim-store",    "data"),
    Output("reco-anim-interval", "disabled"),
    Input("reco-anim-interval",  "n_intervals"),
    State("reco-anim-store",     "data"),
    prevent_initial_call=True,
)


# Rendu de la zone résultat
@callback(
    Output("reco-result-area", "children"),
    Input("reco-result-store", "data"),
)
def render_result(result):
    if not result:
        return _empty_state()

    platform = result.get("platform", "netflix")
    cfg      = PLATFORM_CFG[platform]

    if result.get("found"):
        return _render_found(result, cfg)
    else:
        return _render_not_found(result, cfg)


# ─── RENDERERS ───────────────────────────────────────────────────────────────
def _empty_state():
    return html.Div(
        style={"textAlign": "center", "padding": "60px 0", "color": "var(--text-muted)"},
        children=[
            html.Div("🎯", style={"fontSize": "48px", "marginBottom": "12px"}),
            html.P("Lance une recherche pour voir ton score d'affinité.",
                   style={"fontSize": "15px"}),
        ],
    )


def _render_found(result: dict, cfg: dict):
    score   = result["score"]
    title   = result["title"]
    query   = result["query"]
    plays   = result["plays"]
    ratio   = result["ratio"]
    similar = result.get("similar", [])

    color     = cfg["color"]
    score_c   = _score_color(score)
    score_lbl = _score_label(score)
    verb      = cfg["verb"]

    # Badge correspondance
    if ratio == 1.0:
        match_badge = _badge("Correspondance exacte", "#30d158")
    elif ratio >= 0.9:
        match_badge = _badge(f'Correspondance partielle : "{title}"', "#ffd60a")
    else:
        match_badge = _badge(f'Meilleur match ({int(ratio*100)}%) : "{title}"', "#ff9f0a")

    # Statut vu/écouté
    if plays > 0:
        status_icon, status_txt = "✓", f"Déjà {verb} · {plays:,}×"
        status_color = "#30d158"
    else:
        status_icon, status_txt = "◦", f"Jamais {verb}"
        status_color = "var(--text-muted)"

    return html.Div(children=[

        # ── Score card ────────────────────────────────────────────────────────
        html.Div(
            style={
                "background": f"linear-gradient(145deg, {cfg['dim']} 0%, rgba(28,28,30,0.6) 60%)",
                "border": "1px solid rgba(255,255,255,0.07)",
                "borderTop": f"2px solid {color}",
                "borderRadius": "20px",
                "padding": "36px",
                "marginBottom": "24px",
                "display": "flex",
                "gap": "40px",
                "alignItems": "center",
                "flexWrap": "wrap",
            },
            children=[

                # Cercle score
                html.Div(style={"display": "flex", "flexDirection": "column", "alignItems": "center", "gap": "8px"},
                         children=[
                    html.Div(
                        style={
                            "width": "140px", "height": "140px",
                            "borderRadius": "50%",
                            "border": f"4px solid {score_c}",
                            "display": "flex", "flexDirection": "column",
                            "alignItems": "center", "justifyContent": "center",
                            "background": "rgba(0,0,0,0.4)",
                            "boxShadow": f"0 0 32px {score_c}33",
                            "position": "relative",
                        },
                        children=[
                            html.Span(
                                id="reco-score-counter",
                                children="0%",
                                style={
                                    "fontFamily": "var(--font-serif)",
                                    "fontSize": "36px",
                                    "fontWeight": "600",
                                    "color": score_c,
                                    "lineHeight": "1",
                                },
                            ),
                        ],
                    ),
                    html.Span(score_lbl, style={
                        "fontSize": "12px", "color": "var(--text-muted)",
                        "textAlign": "center", "maxWidth": "140px",
                    }),
                ]),

                # Infos
                html.Div(style={"flex": "1", "minWidth": "200px"}, children=[
                    html.Div(style={"marginBottom": "8px"}, children=[match_badge]),
                    html.H2(title, style={
                        "fontFamily": "var(--font-serif)",
                        "fontSize": "26px", "fontWeight": "500",
                        "color": "var(--text-primary)", "marginBottom": "8px",
                        "lineHeight": "1.2",
                    }),
                    html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px",
                                    "marginBottom": "20px"},
                             children=[
                        html.Span(status_icon, style={"color": status_color, "fontSize": "16px"}),
                        html.Span(status_txt, style={"fontSize": "13px", "color": status_color}),
                    ]),

                    # Barre de progression
                    html.Div(style={"marginBottom": "6px"}, children=[
                        html.Div(style={
                            "height": "6px", "borderRadius": "3px",
                            "background": "rgba(255,255,255,0.08)",
                            "overflow": "hidden",
                        }, children=[
                            html.Div(style={
                                "height": "100%",
                                "width": f"{score:.0f}%",
                                "background": f"linear-gradient(90deg, {cfg['bar']}, {score_c})",
                                "borderRadius": "3px",
                                "transition": "width 1.2s cubic-bezier(0.16, 1, 0.3, 1)",
                            }),
                        ]),
                        html.Div(style={"display": "flex", "justifyContent": "space-between",
                                        "marginTop": "4px"},
                                 children=[
                            html.Span("0", style={"fontSize": "10px", "color": "var(--text-muted)"}),
                            html.Span("100", style={"fontSize": "10px", "color": "var(--text-muted)"}),
                        ]),
                    ]),
                ]),
            ],
        ),

        # ── Similaires ────────────────────────────────────────────────────────
        *(_render_similar(similar, cfg) if similar else []),
    ])


def _render_not_found(result: dict, cfg: dict):
    query     = result.get("query", "")
    top_items = result.get("top_items", [])
    color     = cfg["color"]

    return html.Div(children=[
        # Message
        html.Div(
            style={
                "background": "rgba(28,28,30,0.5)",
                "border": "1px solid rgba(255,255,255,0.07)",
                "borderLeft": f"3px solid {color}",
                "borderRadius": "14px",
                "padding": "24px 28px",
                "marginBottom": "24px",
                "display": "flex", "gap": "16px", "alignItems": "center",
            },
            children=[
                html.Span("🔍", style={"fontSize": "28px"}),
                html.Div(children=[
                    html.Div(f'"{query}" n\'est pas dans ton historique {cfg["label"]}.',
                             style={"fontSize": "15px", "color": "var(--text-primary)",
                                    "marginBottom": "4px"}),
                    html.Div(
                        f"Titre inconnu — pas assez de données pour calculer un score. "
                        f"Voici tes meilleures recommandations {cfg['label']} :",
                        style={"fontSize": "13px", "color": "var(--text-muted)"},
                    ),
                ]),
            ],
        ),

        # Top items
        *(_render_top_grid(top_items, cfg) if top_items else []),
    ])


def _render_similar(items: list, cfg: dict):
    if not items:
        return []
    color = cfg["color"]
    verb  = cfg["verb"]

    cards = []
    for item in items:
        score = float(item.get("predicted_score", 0))
        sc    = _score_color(score)
        plays = int(item.get("play_count", 0))
        cards.append(html.Div(
            style={
                "background": "rgba(28,28,30,0.5)",
                "border": "1px solid rgba(255,255,255,0.06)",
                "borderRadius": "12px",
                "padding": "16px",
                "display": "flex", "flexDirection": "column", "gap": "8px",
            },
            children=[
                html.Div(item.get("item_title", ""), style={
                    "fontSize": "13px", "fontWeight": "500",
                    "color": "var(--text-primary)", "lineHeight": "1.3",
                }),
                html.Div(style={"display": "flex", "justifyContent": "space-between",
                                "alignItems": "center"},
                         children=[
                    html.Span(f"{score:.0f}%", style={
                        "fontFamily": "var(--font-serif)", "fontSize": "18px",
                        "fontWeight": "600", "color": sc,
                    }),
                    html.Span(f"{plays}×", style={"fontSize": "11px", "color": "var(--text-muted)"}),
                ]),
                html.Div(style={
                    "height": "3px", "borderRadius": "2px",
                    "background": "rgba(255,255,255,0.06)",
                    "overflow": "hidden",
                }, children=[
                    html.Div(style={
                        "height": "100%", "width": f"{score:.0f}%",
                        "background": sc, "borderRadius": "2px",
                    }),
                ]),
            ],
        ))

    return [
        html.Div(
            f"Titres similaires que tu as déjà {verb} :",
            style={"fontSize": "13px", "color": "var(--text-muted)",
                   "textTransform": "uppercase", "letterSpacing": "1px",
                   "marginBottom": "12px", "fontWeight": "600"},
        ),
        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fill, minmax(200px, 1fr))",
                "gap": "12px",
            },
            children=cards,
        ),
    ]


def _render_top_grid(items: list, cfg: dict):
    color = cfg["color"]
    cards = []
    for i, item in enumerate(items, 1):
        score = float(item.get("predicted_score", 0))
        sc    = _score_color(score)
        cards.append(html.Div(
            style={
                "background": "rgba(28,28,30,0.5)",
                "border": "1px solid rgba(255,255,255,0.06)",
                "borderTop": f"2px solid {color if i <= 3 else 'rgba(255,255,255,0.1)'}",
                "borderRadius": "12px",
                "padding": "16px",
                "display": "flex", "flexDirection": "column", "gap": "8px",
            },
            children=[
                html.Span(f"#{i}", style={"fontSize": "11px", "color": "var(--text-muted)"}),
                html.Div(item.get("item_title", ""), style={
                    "fontSize": "13px", "fontWeight": "500",
                    "color": "var(--text-primary)", "lineHeight": "1.3",
                }),
                html.Span(f"{score:.0f}%", style={
                    "fontFamily": "var(--font-serif)", "fontSize": "20px",
                    "fontWeight": "600", "color": sc,
                }),
            ],
        ))

    return [
        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fill, minmax(180px, 1fr))",
                "gap": "12px",
            },
            children=cards,
        )
    ]


def _badge(text: str, color: str) -> html.Span:
    return html.Span(text, style={
        "display": "inline-block",
        "fontSize": "11px", "fontWeight": "600",
        "color": color,
        "background": f"{color}22",
        "border": f"1px solid {color}55",
        "borderRadius": "6px",
        "padding": "3px 10px",
        "letterSpacing": "0.3px",
    })
