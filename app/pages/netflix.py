import os
import re
import requests
import pandas as pd
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, callback, dcc, html, no_update, clientside_callback
from app.icons import svg_icon, FILM, TV, VIDEO
from difflib import SequenceMatcher

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = "/app/data/warehouse" if os.path.exists("/app/data/warehouse") else "warehouse"

NETFLIX_RED = "#e50914"
_TMDB_KEY = os.getenv("TMDB_API_KEY", "")
_poster_cache: dict = {}


def _get_poster_url(tmdb_id) -> str:
    """Récupère l'URL du poster TMDB avec cache mémoire."""
    if not tmdb_id or pd.isna(tmdb_id) or not _TMDB_KEY:
        return ""
    tid = int(tmdb_id)
    if tid in _poster_cache:
        return _poster_cache[tid]
    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/movie/{tid}",
            params={"api_key": _TMDB_KEY},
            timeout=3,
        )
        if r.status_code == 200:
            path = r.json().get("poster_path", "")
            url = f"https://image.tmdb.org/t/p/w300{path}" if path else ""
            _poster_cache[tid] = url
            return url
    except Exception:
        pass
    _poster_cache[tid] = ""
    return ""

# ─── DATA ────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_recos() -> pd.DataFrame:
    # Supporte fichier unique (als_fast_local.py) ou dossier (notebook Spark)
    single = os.path.join(DELTA_BASE, "movie_recommendations.parquet")
    if os.path.isfile(single):
        df = pd.read_parquet(single)
    else:
        path = os.path.join(DELTA_BASE, "movie_recommendations")
        if not os.path.exists(path):
            return pd.DataFrame()
        files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".parquet")]
        if not files:
            return pd.DataFrame()
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["title_lower"] = df["title"].str.lower().str.strip()
    return df


MONTH_NAMES = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr",
    5: "Mai", 6: "Jun", 7: "Jul", 8: "Aoû",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc",
}

_PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif", color="#ebebf5"),
    margin=dict(l=16, r=16, t=32, b=16),
)

_DEFAULT_SEL = {"year": None, "months": [], "weeks": []}


# ─── DATA ────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_netflix() -> pd.DataFrame:
    path = os.path.join(DELTA_BASE, "netflix_views")
    if not os.path.exists(path):
        return pd.DataFrame()
    files = [
        os.path.join(path, f)
        for f in os.listdir(path)
        if f.endswith(".parquet") and not f.startswith(".")
    ]
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            cols = ["show_title", "content_type", "watch_date",
                    "watch_year", "watch_month", "watch_weekday", "watch_week", "season"]
            dfs.append(df[[c for c in cols if c in df.columns]])
        except Exception:
            pass
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    df["watch_date"] = pd.to_datetime(df["watch_date"], errors="coerce")
    if "watch_month" in df.columns:
        df["month_int"] = df["watch_month"].str.split("-").str[1].astype(int, errors="ignore")
    return df


def _apply_filter(df: pd.DataFrame, sel: dict) -> pd.DataFrame:
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []
    if year:   df = df[df["watch_year"] == year]
    if months: df = df[df["month_int"].isin(months)]
    if weeks:  df = df[df["watch_week"].isin(weeks)]
    return df


def _years(df: pd.DataFrame) -> list:
    if df.empty or "watch_year" not in df.columns:
        return []
    return sorted(df["watch_year"].dropna().astype(int).unique().tolist())


def _months_for_year(df: pd.DataFrame, year: int) -> list:
    sub = df[df["watch_year"] == year]
    if sub.empty or "month_int" not in sub.columns:
        return []
    return sorted(sub["month_int"].dropna().astype(int).unique().tolist())


def _weeks_for_selection(df: pd.DataFrame, year: int, months: list) -> list:
    sub = df[df["watch_year"] == year]
    if months:
        sub = sub[sub["month_int"].isin(months)]
    if sub.empty or "watch_week" not in sub.columns:
        return []
    return sorted(sub["watch_week"].dropna().astype(int).unique().tolist())


# ─── PERIOD SELECTOR ─────────────────────────────────────────────────────────
def _chip(label: str, chip_type: str, index, is_active: bool) -> html.Span:
    return html.Span(
        label,
        id={"type": chip_type, "index": index if index is not None else "__all__"},
        className=f"filter-chip {'filter-chip-active' if is_active else ''}",
        n_clicks=0,
        style={"cursor": "pointer",
               **({"borderColor": NETFLIX_RED, "color": NETFLIX_RED} if is_active else {})},
    )


def _chip_row(row_label: str, chip_type: str, items: list, active_vals: list) -> html.Div:
    tout_active = len(active_vals) == 0
    return html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "8px", "flexWrap": "wrap"},
        children=[
            html.Span(f"{row_label} :", style={
                "fontSize": "11px", "fontWeight": "600",
                "color": "var(--text-muted)", "textTransform": "uppercase",
                "letterSpacing": "1.5px", "minWidth": "60px",
            }),
            _chip("Tout", chip_type, None, tout_active),
            *[_chip(lbl, chip_type, val, val in active_vals) for val, lbl in items],
        ],
    )


def _active_label(sel: dict) -> str:
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []
    if not year:
        return "Tout l'historique"
    parts = [str(year)]
    if months:
        month_labels = [MONTH_NAMES[m] for m in sorted(months)]
        parts.append(", ".join(month_labels[:3]) + (f" +{len(month_labels)-3}" if len(month_labels) > 3 else ""))
    if weeks:
        week_labels = [f"S{w}" for w in sorted(weeks)]
        parts.append(", ".join(week_labels[:4]) + (f" +{len(week_labels)-4}" if len(week_labels) > 4 else ""))
    return " · ".join(parts)


def _period_selector(df: pd.DataFrame, sel: dict) -> html.Div:
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []

    rows = [
        _chip_row("Année", "netflix-chip-year",
                  [(y, str(y)) for y in _years(df)],
                  [year] if year else []),
    ]

    if year is not None:
        rows.append(_chip_row(
            "Mois", "netflix-chip-month",
            [(m, MONTH_NAMES[m]) for m in _months_for_year(df, year)],
            months,
        ))

    if year is not None:
        avail_weeks = _weeks_for_selection(df, year, months)
        if avail_weeks:
            rows.append(_chip_row(
                "Semaine", "netflix-chip-week",
                [(w, f"S{w}") for w in avail_weeks],
                weeks,
            ))

    return html.Div(
        style={
            "background": "rgba(28,28,30,0.5)",
            "backdropFilter": "blur(40px)",
            "border": "1px solid rgba(255,255,255,0.06)",
            "borderLeft": f"3px solid {NETFLIX_RED}",
            "borderRadius": "14px",
            "padding": "16px 20px",
            "marginBottom": "32px",
            "display": "flex", "flexDirection": "column", "gap": "12px",
        },
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                children=[
                    html.Span("Période", style={
                        "fontSize": "11px", "fontWeight": "700",
                        "color": NETFLIX_RED, "textTransform": "uppercase",
                        "letterSpacing": "2px",
                    }),
                    html.Span(_active_label(sel), style={
                        "fontSize": "13px", "fontWeight": "500",
                        "color": "var(--text-primary)", "fontFamily": "var(--font-serif)",
                    }),
                ],
            ),
            *rows,
        ],
    )


# ─── RECO UTILS ──────────────────────────────────────────────────────────────
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

def _badge(text: str, color: str) -> html.Span:
    return html.Span(text, style={
        "display": "inline-block", "fontSize": "11px", "fontWeight": "600",
        "color": color, "background": f"{color}22", "border": f"1px solid {color}55",
        "borderRadius": "6px", "padding": "3px 10px", "letterSpacing": "0.3px",
    })

def _find_match(query: str, df: pd.DataFrame):
    if df.empty or not query.strip(): return None, 0
    q = query.lower().strip()
    col = "title_lower"
    exact = df[df[col] == q]
    if not exact.empty: return exact.iloc[0], 1.0
    partial = df[df[col].str.contains(re.escape(q), na=False)]
    if not partial.empty: return partial.loc[partial["predicted_score"].idxmax()], 0.9
    best_ratio, best_row = 0.0, None
    for _, row in df.iterrows():
        ratio = SequenceMatcher(None, q, row[col]).ratio()
        if ratio > best_ratio: best_ratio, best_row = ratio, row
    if best_ratio >= 0.55: return best_row, best_ratio
    return None, 0

# ─── RECO COMPONENTS ─────────────────────────────────────────────────────────
def _reco_section():
    recos = _load_recos()
    if recos.empty: return html.Div()
    
    top_10 = recos.sort_values("rank").head(10)
    cards = []
    for _, r in top_10.iterrows():
        sc = _score_color(r["predicted_score"])
        poster_url = _get_poster_url(r.get("tmdbId"))
        genre_label = r["genres"].split("|")[0] if r.get("genres") else "Film"
        cards.append(html.Div(
            style={
                "background": "rgba(28,28,30,0.5)", "border": "1px solid rgba(255,255,255,0.06)",
                "borderRadius": "16px", "overflow": "hidden", "minWidth": "160px", "flex": "1",
                "display": "flex", "flexDirection": "column", "transition": "transform 0.2s",
            },
            children=[
                # Poster
                html.Div(
                    style={"height": "220px", "background": "rgba(255,255,255,0.04)", "position": "relative", "overflow": "hidden"},
                    children=[
                        html.Img(src=poster_url, style={"width": "100%", "height": "100%", "objectFit": "cover"}) if poster_url
                        else html.Div(svg_icon(FILM, size="48"), style={"display": "flex", "alignItems": "center", "justifyContent": "center", "height": "100%", "color": "#555"}),
                        html.Span(f"#{r['rank']}", style={
                            "position": "absolute", "top": "8px", "left": "8px",
                            "background": "rgba(0,0,0,0.75)", "color": NETFLIX_RED if r["rank"] <= 3 else "#fff",
                            "fontSize": "11px", "fontWeight": "800", "padding": "3px 8px", "borderRadius": "6px",
                        }),
                        html.Span(f"{r['predicted_score']:.0f}%", style={
                            "position": "absolute", "bottom": "8px", "right": "8px",
                            "background": "rgba(0,0,0,0.75)", "color": sc,
                            "fontFamily": "var(--font-serif)", "fontSize": "18px", "fontWeight": "700",
                            "padding": "3px 8px", "borderRadius": "6px",
                        }),
                    ]
                ),
                # Infos
                html.Div(style={"padding": "12px 14px", "display": "flex", "flexDirection": "column", "gap": "4px"}, children=[
                    html.Div(r["title"], style={"fontSize": "13px", "fontWeight": "600", "color": "#fff", "lineHeight": "1.3"}),
                    html.Div(genre_label, style={"fontSize": "10px", "color": "var(--text-muted)", "textTransform": "uppercase", "letterSpacing": "0.5px"}),
                ]),
            ]
        ))

    return html.Div(style={"marginTop": "60px"}, children=[
        html.Div(style={"textAlign": "center", "marginBottom": "40px"}, children=[
            html.H2(["Recommandé pour ", html.Em("Toi")], style={"fontSize": "32px", "fontFamily": "var(--font-serif)", "marginBottom": "8px"}),
            html.P("Basé sur ton historique et 32M de notes MovieLens.", style={"color": "var(--text-muted)"})
        ]),
        
        # Moteur de recherche d'affinité
        html.Div(style={"maxWidth": "600px", "margin": "0 auto 48px", "display": "flex", "gap": "12px"}, children=[
            dcc.Input(id="nf-reco-input", type="text", placeholder="Arnaud aimera-t-il le film...", 
                      style={"flex": "1", "background": "rgba(255,255,255,0.05)", "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "12px", "padding": "12px 20px", "color": "#fff"}),
            html.Button("Vérifier", id="nf-reco-btn", n_clicks=0, className="btn-primary", style={"background": NETFLIX_RED, "border": "none", "borderRadius": "12px", "padding": "0 24px", "color": "#fff", "fontWeight": "600"})
        ]),
        dcc.Store(id="nf-reco-result-store"),
        dcc.Store(id="nf-reco-anim-store", data={"target": 0, "current": 0}),
        dcc.Interval(id="nf-reco-anim-interval", interval=25, disabled=True),
        html.Div(id="nf-reco-score-counter", style={"display": "none"}),
        html.Div(id="nf-reco-result-area", style={"marginBottom": "48px"}),

        html.Div(style={"display": "flex", "gap": "16px", "overflowX": "auto", "padding": "10px 0", "marginBottom": "20px"}, children=cards),

        # Toggle Top 50
        html.Div(style={"textAlign": "right"}, children=[
            html.Button(
                "Voir le Top 50 complet →",
                id="nf-top50-btn",
                n_clicks=0,
                style={
                    "background": "none", "border": "none", "cursor": "pointer",
                    "color": NETFLIX_RED, "fontSize": "13px", "fontWeight": "600",
                    "fontFamily": "var(--font-family)", "padding": "4px 0",
                },
            )
        ]),
        html.Div(id="nf-top50-area"),
    ])

# ─── CHARTS ──────────────────────────────────────────────────────────────────

def _fig_defaults(fig: go.Figure) -> go.Figure:
    fig.update_layout(**_PLOTLY_THEME)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False)
    return fig


def _chart_activity(df: pd.DataFrame, sel: dict) -> go.Figure:
    if df.empty:
        return go.Figure()
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []

    if year and weeks:
        grouped = df.groupby("watch_week").size().reset_index(name="count").sort_values("watch_week")
        x_vals  = grouped["watch_week"].apply(lambda w: f"S{w}")
        title   = "Visionnages par semaine"
    elif year and months:
        grouped = df.groupby("month_int").size().reset_index(name="count").sort_values("month_int")
        x_vals  = grouped["month_int"].map(MONTH_NAMES)
        title   = "Visionnages par mois sélectionnés"
    elif year:
        grouped = df.groupby("watch_month").size().reset_index(name="count").sort_values("watch_month")
        x_vals  = grouped["watch_month"]
        title   = f"Visionnages par mois — {year}"
    else:
        grouped = df.groupby("watch_month").size().reset_index(name="count").sort_values("watch_month")
        x_vals  = grouped["watch_month"]
        title   = "Activité mensuelle (tout l'historique)"

    fig = go.Figure(go.Bar(
        x=x_vals, y=grouped["count"],
        marker_color=NETFLIX_RED, marker_opacity=0.85,
        hovertemplate="%{x}<br><b>%{y} visionnages</b><extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#8e8e93"), x=0),
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        **_PLOTLY_THEME,
    )
    return _fig_defaults(fig)


def _chart_weekday(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    day_map = {1: "Dim", 2: "Lun", 3: "Mar", 4: "Mer", 5: "Jeu", 6: "Ven", 7: "Sam"}
    df2 = df.copy()
    df2["day_label"] = df2["watch_weekday"].map(day_map)
    order  = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    counts = df2.groupby("day_label").size().reindex(order, fill_value=0)
    fig = go.Figure(go.Bar(
        x=counts.index, y=counts.values,
        marker_color=[NETFLIX_RED if d in ["Sam", "Dim"] else "rgba(229,9,20,0.45)" for d in counts.index],
        hovertemplate="%{x}<br><b>%{y} visionnages</b><extra></extra>",
    ))
    fig.update_layout(title=dict(text="Jour de la semaine", font=dict(size=14, color="#8e8e93"), x=0),
                      **_PLOTLY_THEME)
    return _fig_defaults(fig)


def _chart_by_year(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    yearly = df.groupby(["watch_year", "content_type"]).size().reset_index(name="count")
    fig = go.Figure()
    for ctype, color in [("series", NETFLIX_RED), ("movie", "rgba(255,255,255,0.5)")]:
        sub = yearly[yearly["content_type"] == ctype]
        if sub.empty:
            continue
        label = "Séries" if ctype == "series" else "Films"
        fig.add_trace(go.Bar(
            name=label, x=sub["watch_year"].astype(str), y=sub["count"],
            marker_color=color,
            hovertemplate=f"{label} — %{{x}}<br><b>%{{y}} visionnages</b><extra></extra>",
        ))
    fig.update_layout(
        barmode="stack",
        title=dict(text="Séries vs Films par année", font=dict(size=14, color="#8e8e93"), x=0),
        legend=dict(orientation="h", x=0, y=1.1),
        **_PLOTLY_THEME,
    )
    return _fig_defaults(fig)


# ─── CONTENT BUILDER ─────────────────────────────────────────────────────────
def _build_content(df: pd.DataFrame, sel: dict) -> list:
    if df.empty:
        return [html.P("Aucune donnée pour cette période.",
                       style={"color": "var(--text-muted)", "padding": "20px 0"})]

    total    = len(df)
    n_series = df[df["content_type"] == "series"]["show_title"].nunique() if "content_type" in df.columns else 0
    n_movies = df[df["content_type"] == "movie"]["show_title"].nunique()  if "content_type" in df.columns else 0

    panel = {
        "background": "rgba(28,28,30,0.5)",
        "backdropFilter": "blur(40px)",
        "border": "1px solid rgba(255,255,255,0.06)",
        "borderRadius": "14px",
        "padding": "20px",
    }

    def _stat(icon, value, label):
        return html.Div(className="stat-card", children=[
            html.Div(icon,  className="stat-icon"),
            html.Div(value, className="stat-value"),
            html.Div(label, className="stat-label"),
        ])

    top_series = (
        df[df["content_type"] == "series"]
        .groupby("show_title").size().reset_index(name="count")
        .sort_values("count", ascending=False).head(10)
    ) if "content_type" in df.columns else pd.DataFrame()

    top_movies = (
        df[df["content_type"] == "movie"]
        .groupby("show_title").size().reset_index(name="count")
        .sort_values("count", ascending=False).head(10)
    ) if "content_type" in df.columns else pd.DataFrame()

    def _rank_list(rows_df, color=NETFLIX_RED):
        items = []
        for i, (_, row) in enumerate(rows_df.iterrows(), 1):
            items.append(html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "12px",
                       "padding": "10px 0", "borderBottom": "1px solid rgba(255,255,255,0.05)"},
                children=[
                    html.Span(f"{i:02d}", style={
                        "fontFamily": "var(--font-serif)", "fontSize": "20px",
                        "color": color if i <= 3 else "var(--text-muted)", "minWidth": "28px",
                    }),
                    html.Span(row["show_title"], style={
                        "fontSize": "14px", "color": "var(--text-primary)", "flex": "1",
                    }),
                    html.Span(f"{row['count']}×", style={"fontSize": "12px", "color": "var(--text-muted)"}),
                ],
            ))
        return items

    def _section_card(title, children):
        return html.Div(
            style={**panel, "borderTop": f"2px solid {NETFLIX_RED}", "flex": "1", "minWidth": "280px"},
            children=[
                html.H3(title, style={"fontFamily": "var(--font-serif)", "fontSize": "18px",
                                      "color": "var(--text-primary)", "marginBottom": "16px"}),
                *children,
            ],
        )

    # Seulement le graphe annuel si pas de filtre année
    show_yearly = sel.get("year") is None

    return [
        html.Div(className="stats-row", style={"marginBottom": "24px", "marginLeft": "auto", "marginRight": "auto"}, children=[
            _stat(svg_icon(FILM),  f"{total:,}",    "Épisodes / Films"),
            _stat(svg_icon(TV),    f"{n_series:,}", "Séries distinctes"),
            _stat(svg_icon(VIDEO), f"{n_movies:,}", "Films regardés"),
        ]),

        html.Div(style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "marginTop": "24px"},
                 children=[
            html.Div(style={**panel, "flex": "2", "minWidth": "340px"},
                     children=[dcc.Graph(figure=_chart_activity(df, sel),
                                         config={"displayModeBar": False})]),
            html.Div(style={**panel, "flex": "1", "minWidth": "240px"},
                     children=[dcc.Graph(figure=_chart_weekday(df),
                                         config={"displayModeBar": False})]),
        ]),

        *([html.Div(style={**panel, "marginTop": "16px"},
                    children=[dcc.Graph(figure=_chart_by_year(df),
                                         config={"displayModeBar": False})])]
          if show_yearly else []),

        html.Div(style={"marginTop": "24px", "display": "flex", "gap": "16px", "flexWrap": "wrap"},
                 children=[
            _section_card("Top Séries", _rank_list(top_series) if not top_series.empty else [html.P("—")]),
            _section_card("Top Films",  _rank_list(top_movies, color="rgba(255,255,255,0.6)")
                          if not top_movies.empty else [html.P("—")]),
        ]),
    ]


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    df = _load_netflix()

    if df.empty:
        return html.Div(className="page-wrapper", children=[
            html.Div(
                style={"display": "flex", "flexDirection": "column", "alignItems": "center",
                       "justifyContent": "center", "height": "calc(100vh - 52px)", "gap": "16px"},
                children=[
                    html.Div(svg_icon(FILM, size="56"), style={"color": "var(--text-secondary)"}),
                    html.H2("Netflix", style={"fontSize": "28px", "fontWeight": "700",
                                              "color": "var(--text-primary)"}),
                    html.P("Lance d'abord 01_exploration/netflix.ipynb.",
                           style={"fontSize": "14px", "color": "var(--text-secondary)"}),
                ],
            )
        ])

    return html.Div(className="page-wrapper", children=[
        html.Div(
            style={"maxWidth": "1100px", "margin": "0 auto", "padding": "40px 32px 80px"},
            children=[
                html.Div(className="home-hero", style={"textAlign": "center"}, children=[
                    html.P("Historique Netflix • Année · Mois · Semaine",
                            className="home-hero-label", style={"color": NETFLIX_RED}),
                    html.H1(html.Span(["Mon ", html.Em("Netflix")]),
                             className="home-hero-title", style={"fontSize": "56px"}),
                    html.P("Timeline de tes visionnages, tes séries et films favoris.",
                            className="home-hero-sub"),
                ]),
                dcc.Store(id="netflix-sel-store", data=_DEFAULT_SEL),

                html.Div(id="netflix-period-selector",
                         children=_period_selector(df, _DEFAULT_SEL)),

                html.Div(id="netflix-content",
                         children=_build_content(df, _DEFAULT_SEL)),

                html.Div(id="netflix-recos",
                         children=_reco_section()),
            ],
        )
    ])


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
@callback(
    Output("nf-top50-area",  "children"),
    Output("nf-top50-btn",   "children"),
    Input("nf-top50-btn",    "n_clicks"),
    prevent_initial_call=True,
)
def toggle_top50(n_clicks):
    if n_clicks % 2 == 0:
        return html.Div(), "Voir le Top 50 complet →"

    recos = _load_recos()
    if recos.empty:
        return html.Div("Aucune donnée.", style={"color": "var(--text-muted)"}), "Masquer ↑"

    rows = []
    for _, r in recos.sort_values("rank").iterrows():
        sc = _score_color(r["predicted_score"])
        genre = (r.get("genres") or "").split("|")[0]
        rows.append(html.Div(
            style={
                "display": "flex", "alignItems": "center", "gap": "16px",
                "padding": "10px 0", "borderBottom": "1px solid rgba(255,255,255,0.05)",
            },
            children=[
                html.Span(f"{int(r['rank']):02d}", style={
                    "fontFamily": "var(--font-serif)", "fontSize": "18px", "minWidth": "32px",
                    "color": NETFLIX_RED if r["rank"] <= 3 else "var(--text-muted)",
                }),
                html.Span(r["title"], style={"flex": "1", "fontSize": "14px", "color": "var(--text-primary)"}),
                html.Span(genre, style={"fontSize": "11px", "color": "var(--text-muted)", "minWidth": "80px"}),
                html.Span(f"{r['predicted_score']:.0f}%", style={
                    "fontFamily": "var(--font-serif)", "fontSize": "16px",
                    "fontWeight": "600", "color": sc, "minWidth": "48px", "textAlign": "right",
                }),
            ],
        ))

    content = html.Div(
        style={
            "background": "rgba(28,28,30,0.5)", "border": "1px solid rgba(255,255,255,0.06)",
            "borderTop": f"2px solid {NETFLIX_RED}", "borderRadius": "14px",
            "padding": "20px 24px", "marginTop": "12px",
        },
        children=[
            html.H3("Top 50 — Films recommandés", style={
                "fontFamily": "var(--font-serif)", "fontSize": "18px",
                "color": "var(--text-primary)", "marginBottom": "16px",
            }),
            *rows,
        ],
    )
    return content, "Masquer ↑"


@callback(
    Output("nf-reco-result-store",  "data"),
    Output("nf-reco-anim-store",    "data",     allow_duplicate=True),
    Output("nf-reco-anim-interval", "disabled", allow_duplicate=True),
    Output("nf-reco-anim-interval", "n_intervals"),
    Input("nf-reco-btn", "n_clicks"),
    Input("nf-reco-input", "n_submit"),
    State("nf-reco-input", "value"),
    prevent_initial_call=True,
)
def do_nf_search(n1, n2, query):
    if not query or not query.strip(): return no_update, no_update, True, no_update
    df = _load_recos()
    row, ratio = _find_match(query, df)
    if row is not None:
        result = {
            "found": True, "title": row["title"], "query": query.strip(),
            "score": float(row["predicted_score"]), "rank": int(row.get("rank", 0)),
            "genres": row.get("genres", ""), "ratio": round(ratio, 2),
        }
    else:
        result = {"found": False, "query": query.strip()}
    anim = {"target": int(result.get("score", 0)), "current": 0}
    return result, anim, False, 0

clientside_callback(
    """
    function(n, store) {
        if (!store || store.target === 0) return [window.dash_clientside.no_update, store, true];
        var current = store.current || 0;
        var target  = store.target  || 0;
        if (current >= target) return [target + "%", store, true];
        var step = Math.max(1, Math.ceil((target - current) / 12));
        var next = Math.min(current + step, target);
        return [next + "%", {target: target, current: next}, next >= target];
    }
    """,
    Output("nf-reco-score-counter", "children"),
    Output("nf-reco-anim-store",    "data"),
    Output("nf-reco-anim-interval", "disabled"),
    Input("nf-reco-anim-interval",  "n_intervals"),
    State("nf-reco-anim-store",     "data"),
    prevent_initial_call=True,
)

@callback(
    Output("nf-reco-result-area", "children"),
    Input("nf-reco-result-store", "data"),
)
def render_nf_result(result):
    if not result: return html.Div()
    if not result.get("found"):
        return html.Div(
            f"'{result['query']}' n'est pas dans les recommandations (pas de données MovieLens suffisantes).",
            style={"color": "var(--text-muted)", "textAlign": "center", "marginTop": "20px"},
        )

    sc = _score_color(result["score"])
    rank = result.get("rank", 0)
    genre = (result.get("genres") or "").split("|")[0]
    rank_badge = html.Span(
        f"#{rank} dans ton top",
        style={
            "fontSize": "11px", "fontWeight": "700", "color": NETFLIX_RED,
            "background": f"{NETFLIX_RED}22", "border": f"1px solid {NETFLIX_RED}55",
            "borderRadius": "6px", "padding": "3px 10px",
        }
    ) if rank else html.Span()

    return html.Div(style={
        "background": "rgba(229,9,20,0.08)", "border": f"1px solid {NETFLIX_RED}44",
        "borderRadius": "16px", "padding": "24px", "display": "flex", "alignItems": "center", "gap": "24px",
    }, children=[
        html.Div(id="nf-reco-score-counter", children="0%", style={
            "fontSize": "42px", "fontWeight": "700", "color": sc, "minWidth": "90px",
            "fontFamily": "var(--font-serif)",
        }),
        html.Div(children=[
            html.Div(result["title"], style={"fontSize": "20px", "fontWeight": "600", "color": "#fff", "marginBottom": "6px"}),
            html.Div(style={"display": "flex", "gap": "8px", "alignItems": "center", "flexWrap": "wrap"}, children=[
                rank_badge,
                html.Span(_score_label(result["score"]), style={"fontSize": "13px", "color": "var(--text-muted)"}),
                *([html.Span(genre, style={"fontSize": "11px", "color": "var(--text-muted)"})] if genre else []),
            ]),
        ]),
    ])
@callback(
    Output("netflix-sel-store", "data"),
    Input({"type": "netflix-chip-year",  "index": ALL}, "n_clicks"),
    Input({"type": "netflix-chip-month", "index": ALL}, "n_clicks"),
    Input({"type": "netflix-chip-week",  "index": ALL}, "n_clicks"),
    State({"type": "netflix-chip-year",  "index": ALL}, "id"),
    State({"type": "netflix-chip-month", "index": ALL}, "id"),
    State({"type": "netflix-chip-week",  "index": ALL}, "id"),
    State("netflix-sel-store", "data"),
    prevent_initial_call=True,
)
def update_selection(*args):
    from dash import ctx
    store = args[-1] or _DEFAULT_SEL

    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
        return store

    chip_type = ctx.triggered_id.get("type", "")
    index     = ctx.triggered_id.get("index", "__all__")
    val       = None if index == "__all__" else int(index)

    if chip_type == "netflix-chip-year":
        new_year = None if (val == store.get("year")) else val
        return {"year": new_year, "months": [], "weeks": []}

    if chip_type == "netflix-chip-month":
        months = list(store.get("months") or [])
        if val is None:
            return {**store, "months": [], "weeks": []}
        if val in months:
            months.remove(val)
        else:
            months.append(val)
        return {**store, "months": months, "weeks": []}

    if chip_type == "netflix-chip-week":
        weeks = list(store.get("weeks") or [])
        if val is None:
            return {**store, "weeks": []}
        if val in weeks:
            weeks.remove(val)
        else:
            weeks.append(val)
        return {**store, "weeks": weeks}

    return store


@callback(
    Output("netflix-period-selector", "children"),
    Output("netflix-content",         "children"),
    Input("netflix-sel-store",        "data"),
)
def refresh_view(sel):
    sel      = sel or _DEFAULT_SEL
    df       = _load_netflix()
    filtered = _apply_filter(df, sel)
    return _period_selector(df, sel), _build_content(filtered, sel)
