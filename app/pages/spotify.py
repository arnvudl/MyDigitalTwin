import os
import pandas as pd
import plotly.graph_objects as go
from functools import lru_cache
from dash import ALL, Input, Output, State, callback, dcc, html
from app.icons import svg_icon, MUSIC, CLOCK, MIC

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = "/app/data/warehouse" if os.path.exists("/app/data/warehouse") else "warehouse"

SPOTIFY_GREEN = "#1db954"

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

# Store shape : {"year": int|None, "months": list[int], "weeks": list[int]}
_DEFAULT_SEL = {"year": None, "months": [], "weeks": []}


# ─── DATA ────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_spotify() -> pd.DataFrame:
    path = os.path.join(DELTA_BASE, "spotify_streams")
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
            cols = ["artistName", "trackName", "msPlayed", "minutes_played",
                    "listen_ts", "listen_hour", "listen_weekday",
                    "listen_year", "listen_month", "listen_week"]
            dfs.append(df[[c for c in cols if c in df.columns]])
        except Exception:
            pass
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    if "listen_ts" in df.columns:
        df["listen_ts"] = pd.to_datetime(df["listen_ts"], errors="coerce")
    if "listen_month" in df.columns:
        df["month_int"] = df["listen_month"].str.split("-").str[1].astype(int, errors="ignore")
    return df


def _apply_filter(df: pd.DataFrame, sel: dict) -> pd.DataFrame:
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []
    if year:   df = df[df["listen_year"] == year]
    if months: df = df[df["month_int"].isin(months)]
    if weeks:  df = df[df["listen_week"].isin(weeks)]
    return df


def _years(df: pd.DataFrame) -> list:
    if df.empty or "listen_year" not in df.columns:
        return []
    return sorted(df["listen_year"].dropna().astype(int).unique().tolist())


def _months_for_year(df: pd.DataFrame, year: int) -> list:
    sub = df[df["listen_year"] == year]
    if sub.empty or "month_int" not in sub.columns:
        return []
    return sorted(sub["month_int"].dropna().astype(int).unique().tolist())


def _weeks_for_selection(df: pd.DataFrame, year: int, months: list) -> list:
    sub = df[df["listen_year"] == year]
    if months:
        sub = sub[sub["month_int"].isin(months)]
    if sub.empty or "listen_week" not in sub.columns:
        return []
    return sorted(sub["listen_week"].dropna().astype(int).unique().tolist())


# ─── PERIOD SELECTOR ─────────────────────────────────────────────────────────
def _chip(label: str, chip_type: str, index, is_active: bool) -> html.Span:
    return html.Span(
        label,
        id={"type": chip_type, "index": index if index is not None else "__all__"},
        className=f"filter-chip {'filter-chip-active' if is_active else ''}",
        n_clicks=0,
        style={"cursor": "pointer",
               **({"borderColor": SPOTIFY_GREEN, "color": SPOTIFY_GREEN} if is_active else {})},
    )


def _chip_row(row_label: str, chip_type: str, items: list, active_vals: list) -> html.Div:
    """
    items       : list of (int_value, display_label)
    active_vals : list of selected int values ([] = "Tout" active)
    """
    tout_active = len(active_vals) == 0
    chips = [
        _chip("Tout", chip_type, None, tout_active),
        *[_chip(lbl, chip_type, val, val in active_vals) for val, lbl in items],
    ]
    return html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "8px", "flexWrap": "wrap"},
        children=[
            html.Span(f"{row_label} :", className="filter-row-label"),
            *chips,
        ],
    )


def _active_label(sel: dict) -> str:
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []
    if not year:
        return "Toutes les écoutes"
    parts = [str(year)]
    if months:
        month_labels = [MONTH_NAMES[m] for m in sorted(months)]
        if len(month_labels) > 3:
            parts.append(f"{', '.join(month_labels[:3])} +{len(month_labels)-3}")
        else:
            parts.append(", ".join(month_labels))
    if weeks:
        week_labels = [f"S{w}" for w in sorted(weeks)]
        if len(week_labels) > 4:
            parts.append(f"{', '.join(week_labels[:4])} +{len(week_labels)-4}")
        else:
            parts.append(", ".join(week_labels))
    return " · ".join(parts)


def _period_selector(df: pd.DataFrame, sel: dict) -> html.Div:
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []

    rows = []

    # Niveau 1 — Années (single select)
    years = _years(df)
    rows.append(_chip_row(
        "Année", "spotify-chip-year",
        [(y, str(y)) for y in years],
        [year] if year else [],
    ))

    # Niveau 2 — Mois (multi-select), visible si une année est sélectionnée
    if year is not None:
        avail_months = _months_for_year(df, year)
        rows.append(_chip_row(
            "Mois", "spotify-chip-month",
            [(m, MONTH_NAMES[m]) for m in avail_months],
            months,
        ))

    # Niveau 3 — Semaines (multi-select), visible si une année est sélectionnée
    if year is not None:
        avail_weeks = _weeks_for_selection(df, year, months)
        if avail_weeks:
            rows.append(_chip_row(
                "Semaine", "spotify-chip-week",
                [(w, f"S{w}") for w in avail_weeks],
                weeks,
            ))

    return html.Div(
        style={
            "background": "rgba(28,28,30,0.5)",
            "backdropFilter": "blur(40px)",
            "border": "1px solid rgba(255,255,255,0.06)",
            "borderLeft": f"3px solid {SPOTIFY_GREEN}",
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
                        "color": SPOTIFY_GREEN, "textTransform": "uppercase",
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


from app.spotify_utils import spotify_meta

# ─── CHARTS ──────────────────────────────────────────────────────────────────
def _fig_defaults(fig: go.Figure) -> go.Figure:
    fig.update_layout(**_PLOTLY_THEME)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False)
    return fig


def _render_top_artists_visual(df: pd.DataFrame, n: int = 6) -> html.Div:
    if df.empty:
        return html.Div()

    top = (
        df.groupby("artistName")
        .agg(streams=("trackName", "count"))
        .reset_index().sort_values("streams", ascending=False).head(n)
    )

    # Pré-chargement parallèle des images manquantes, une seule sauvegarde cache
    spotify_meta.prefetch_artists(top["artistName"].tolist())

    cards = []
    for _, row in top.iterrows():
        img_url = spotify_meta.get_artist_image(row["artistName"])
        
        # Fallback visuel local si pas d'image
        img_component = html.Img(src=img_url, style={"width": "100%", "height": "100%", "objectFit": "cover"}) if img_url else \
                        html.Div(
                            svg_icon(MIC, size="32"),
                            style={
                                "display": "flex", "alignItems": "center", "justifyContent": "center",
                                "width": "100%", "height": "100%", "color": "#888", "background": "linear-gradient(135deg, #282828, #121212)"
                            })

        cards.append(html.Div(
            style={
                "display": "flex", "flexDirection": "column", "alignItems": "center",
                "width": "120px", "gap": "10px", "textAlign": "center"
            },
            children=[
                html.Div(
                    style={
                        "width": "100px", "height": "100px", "borderRadius": "50%",
                        "overflow": "hidden", "boxShadow": "0 8px 24px rgba(0,0,0,0.3)",
                        "background": "#282828", "border": "1px solid rgba(255,255,255,0.1)"
                    },
                    children=[img_component]
                ),
                html.Div([
                    html.Div(row["artistName"], style={
                        "fontSize": "13px", "fontWeight": "600", "color": "white",
                        "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis", "width": "110px"
                    }),
                    html.Div(f"{row['streams']} streams", style={"fontSize": "11px", "color": SPOTIFY_GREEN})
                ])
            ]
        ))
        
    return html.Div(
        style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "justifyContent": "center", "padding": "20px 0"},
        children=cards
    )


def _render_playlist_visual(df: pd.DataFrame, n: int = 10) -> html.Div:
    if df.empty:
        return html.Div()

    top = (
        df.groupby(["trackName", "artistName"])
        .agg(streams=("msPlayed", "count"), minutes=("minutes_played", "sum"))
        .reset_index().sort_values("streams", ascending=False).head(n)
    )

    # Pré-chargement parallèle des pochettes manquantes, une seule sauvegarde cache
    spotify_meta.prefetch_tracks(
        list(zip(top["trackName"].tolist(), top["artistName"].tolist()))
    )

    rows = []
    for i, (_, row) in enumerate(top.iterrows()):
        img_url = spotify_meta.get_track_image(row["trackName"], row["artistName"])
        rows.append(html.Div(
            style={
                "display": "flex", "alignItems": "center", "padding": "8px 12px",
                "borderRadius": "8px", "gap": "16px", "transition": "background 0.2s",
                "cursor": "default"
            },
            className="playlist-row",
            children=[
                html.Span(str(i+1), style={"width": "20px", "color": "var(--text-muted)", "fontSize": "13px"}),
                html.Img(src=img_url or "https://via.placeholder.com/40?text=Album",
                         style={"width": "40px", "height": "40px", "borderRadius": "4px"}),
                html.Div(style={"flex": "1", "minWidth": "0"}, children=[
                    html.Div(row["trackName"], style={
                        "fontSize": "14px", "fontWeight": "500", "color": "white",
                        "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"
                    }),
                    html.Div(row["artistName"], style={"fontSize": "12px", "color": "var(--text-muted)"})
                ]),
                html.Div(f"{row['streams']} plays", style={
                    "fontSize": "12px", "color": "var(--text-muted)", "width": "80px", "textAlign": "right"
                }),
                html.Div(f"{int(row['minutes'])}m", style={
                    "fontSize": "12px", "color": "var(--text-muted)", "width": "50px", "textAlign": "right"
                })
            ]
        ))
        
    return html.Div(
        style={
            "display": "flex", "flexDirection": "column", "gap": "4px",
            "background": "rgba(0,0,0,0.2)", "borderRadius": "12px", "padding": "12px"
        },
        children=[
            html.Div(style={"display": "flex", "padding": "0 12px 8px", "borderBottom": "1px solid rgba(255,255,255,0.05)", "marginBottom": "8px"}, children=[
                html.Span("#", style={"width": "20px", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase"}),
                html.Span("", style={"width": "40px"}),
                html.Span("Titre", style={"flex": "1", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase"}),
                html.Span("Écoutes", style={"width": "80px", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase", "textAlign": "right"}),
                html.Span("Durée", style={"width": "50px", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase", "textAlign": "right"}),
            ]),
            *rows
        ]
    )


def _chart_top_artists(df: pd.DataFrame, n: int = 15) -> go.Figure:
    if df.empty:
        return go.Figure()
    top = (
        df.groupby("artistName")
        .agg(streams=("trackName", "count"), minutes=("minutes_played", "sum"))
        .reset_index().sort_values("streams", ascending=True).tail(n)
    )
    fig = go.Figure(go.Bar(
        x=top["streams"], y=top["artistName"], orientation="h",
        marker_color=SPOTIFY_GREEN, marker_opacity=0.85,
        customdata=top["minutes"].round(0),
        hovertemplate="<b>%{y}</b><br>%{x} streams · %{customdata:.0f} min<extra></extra>",
    ))
    fig.update_layout(title=dict(text="Top artistes", font=dict(size=14, color="#8e8e93"), x=0),
                      height=380, **_PLOTLY_THEME)
    return _fig_defaults(fig)


def _chart_top_tracks(df: pd.DataFrame, n: int = 15) -> go.Figure:
    if df.empty:
        return go.Figure()
    top = (
        df.groupby(["trackName", "artistName"])
        .agg(streams=("msPlayed", "count"), minutes=("minutes_played", "sum"))
        .reset_index().sort_values("streams", ascending=True).tail(n)
    )
    top["label"] = top["trackName"].str[:35] + " — " + top["artistName"].str[:20]
    fig = go.Figure(go.Bar(
        x=top["streams"], y=top["label"], orientation="h",
        marker_color="rgba(29,185,84,0.6)",
        customdata=top["minutes"].round(0),
        hovertemplate="<b>%{y}</b><br>%{x} streams · %{customdata:.0f} min<extra></extra>",
    ))
    fig.update_layout(title=dict(text="Top titres", font=dict(size=14, color="#8e8e93"), x=0),
                      height=380, **_PLOTLY_THEME)
    return _fig_defaults(fig)


def _chart_activity(df: pd.DataFrame, sel: dict) -> go.Figure:
    if df.empty:
        return go.Figure()
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []

    if year and weeks:
        grouped = df.groupby("listen_week").agg(streams=("trackName", "count")).reset_index()
        grouped = grouped.sort_values("listen_week")
        x_vals  = grouped["listen_week"].apply(lambda w: f"S{w}")
        title   = "Écoutes par semaine"
    elif year and months:
        grouped = df.groupby("month_int").agg(streams=("trackName", "count")).reset_index()
        grouped = grouped.sort_values("month_int")
        x_vals  = grouped["month_int"].map(MONTH_NAMES)
        title   = "Écoutes par mois sélectionnés"
    elif year:
        grouped = df.groupby("listen_month").agg(streams=("trackName", "count")).reset_index()
        grouped = grouped.sort_values("listen_month")
        x_vals  = grouped["listen_month"]
        title   = f"Écoutes par mois — {year}"
    else:
        grouped = df.groupby("listen_month").agg(streams=("trackName", "count")).reset_index()
        grouped = grouped.sort_values("listen_month")
        x_vals  = grouped["listen_month"]
        title   = "Activité mensuelle (toutes années)"

    fig = go.Figure(go.Bar(
        x=x_vals, y=grouped["streams"],
        marker_color=SPOTIFY_GREEN, marker_opacity=0.75,
        hovertemplate="%{x}<br><b>%{y} streams</b><extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#8e8e93"), x=0),
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        **_PLOTLY_THEME,
    )
    return _fig_defaults(fig)


def _chart_hourly(df: pd.DataFrame) -> go.Figure:
    if df.empty or "listen_hour" not in df.columns:
        return go.Figure()
    hourly = df.groupby("listen_hour").size().reset_index(name="count")
    all_h  = pd.DataFrame({"listen_hour": range(24)})
    hourly = all_h.merge(hourly, on="listen_hour", how="left").fillna(0)
    fig = go.Figure(go.Bar(
        x=hourly["listen_hour"], y=hourly["count"],
        marker_color=[SPOTIFY_GREEN if (h >= 20 or h < 6) else "rgba(29,185,84,0.4)"
                      for h in hourly["listen_hour"]],
        hovertemplate="%{x}h<br><b>%{y} écoutes</b><extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Distribution horaire", font=dict(size=14, color="#8e8e93"), x=0),
        xaxis=dict(tickmode="linear", dtick=2),
        **_PLOTLY_THEME,
    )
    return _fig_defaults(fig)


# ─── CONTENT BUILDER ─────────────────────────────────────────────────────────
def _build_content(df: pd.DataFrame, sel: dict) -> list:
    if df.empty:
        return [html.P("Aucune donnée pour cette période.",
                       style={"color": "var(--text-muted)", "padding": "20px 0"})]

    total_streams = len(df)
    total_minutes = int(df["minutes_played"].sum()) if "minutes_played" in df.columns else 0
    total_hours   = total_minutes // 60
    n_artists     = df["artistName"].nunique()
    n_tracks      = df["trackName"].nunique()

    def _stat(icon, value, label):
        return html.Div(className="stat-card", children=[
            html.Div(icon,  className="stat-icon"),
            html.Div(value, className="stat-value"),
            html.Div(label, className="stat-label"),
        ])

    return [
        html.Div(className="stats-row", style={"marginBottom": "24px", "marginLeft": "auto", "marginRight": "auto"}, children=[
            _stat(svg_icon(MUSIC), f"{total_streams:,}", "Streams"),
            _stat(svg_icon(CLOCK), f"{total_hours:,}h",  "Écoutées"),
            _stat(svg_icon(MIC),   f"{n_artists:,}",     "Artistes"),
            _stat(svg_icon(MUSIC), f"{n_tracks:,}",      "Titres distincts"),
        ]),

        # --- TOP ARTISTES VISUEL ---
        html.Div(className="data-panel", style={"marginBottom": "24px"}, children=[
            html.Div("Top Artistes", style={
                "fontSize": "11px", "fontWeight": "700", "color": SPOTIFY_GREEN,
                "textTransform": "uppercase", "letterSpacing": "2px", "marginBottom": "16px"
            }),
            _render_top_artists_visual(df)
        ]),

        # --- PLAYLIST VISUELLE (FULL WIDTH) ---
        html.Div(className="data-panel", style={"marginBottom": "24px"},
                 children=[
            html.Div("Ma Playlist du moment", style={
                "fontSize": "11px", "fontWeight": "700", "color": SPOTIFY_GREEN,
                "textTransform": "uppercase", "letterSpacing": "2px", "marginBottom": "16px"
            }),
            _render_playlist_visual(df, n=12)
        ]),

        # --- GRAPHIQUES DE VARIÉTÉ ET ACTIVITÉ ---
        html.Div(style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
                 children=[
            html.Div(className="data-panel", style={"flex": "1.5", "minWidth": "340px"},
                     children=[dcc.Graph(figure=_chart_activity(df, sel),
                                         config={"displayModeBar": False})]),
            html.Div(className="data-panel", style={"flex": "1", "minWidth": "300px"},
                     children=[dcc.Graph(figure=_chart_hourly(df),
                                         config={"displayModeBar": False})]),
        ]),
    ]


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    df = _load_spotify()

    if df.empty:
        return html.Div(className="page-wrapper", children=[
            html.Div(className="page-empty-state", children=[
                html.Div(svg_icon(MUSIC, size="56"), style={"color": "var(--text-secondary)"}),
                html.H2("Spotify", style={"fontSize": "28px", "fontWeight": "700",
                                          "color": "var(--text-primary)"}),
                html.P("Lance d'abord 01_exploration/spotify.ipynb.",
                       style={"fontSize": "14px", "color": "var(--text-secondary)"}),
            ])
        ])

    return html.Div(className="page-wrapper", children=[
        html.Div(
            style={"maxWidth": "1100px", "margin": "0 auto", "padding": "40px 32px 80px"},
            children=[
                html.Div(className="home-hero", style={"textAlign": "center"}, children=[
                    html.P("Wrapped Custom • Année · Mois · Semaine",
                            className="home-hero-label", style={"color": SPOTIFY_GREEN}),
                    html.H1(html.Span(["Mon ", html.Em("Spotify")]),
                             className="home-hero-title", style={"fontSize": "56px"}),
                    html.P("Choisis une période et explore tes écoutes.",
                            className="home-hero-sub"),
                ]),
                dcc.Store(id="spotify-sel-store", data=_DEFAULT_SEL),

                html.Div(id="spotify-period-selector",
                         children=_period_selector(df, _DEFAULT_SEL)),

                html.Div(id="spotify-content",
                         children=_build_content(df, _DEFAULT_SEL)),
            ],
        )
    ])


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
@callback(
    Output("spotify-sel-store", "data"),
    Input({"type": "spotify-chip-year",  "index": ALL}, "n_clicks"),
    Input({"type": "spotify-chip-month", "index": ALL}, "n_clicks"),
    Input({"type": "spotify-chip-week",  "index": ALL}, "n_clicks"),
    State({"type": "spotify-chip-year",  "index": ALL}, "id"),
    State({"type": "spotify-chip-month", "index": ALL}, "id"),
    State({"type": "spotify-chip-week",  "index": ALL}, "id"),
    State("spotify-sel-store", "data"),
    prevent_initial_call=True,
)
def update_selection(*args):
    from dash import ctx
    store = args[-1] or {"year": None, "months": [], "weeks": []}

    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
        return store

    chip_type = ctx.triggered_id.get("type", "")
    index     = ctx.triggered_id.get("index", "__all__")
    val       = None if index == "__all__" else int(index)

    if chip_type == "spotify-chip-year":
        # Single select : changer d'année reset mois + semaines
        new_year = None if (val == store.get("year")) else val
        return {"year": new_year, "months": [], "weeks": []}

    if chip_type == "spotify-chip-month":
        months = list(store.get("months") or [])
        if val is None:
            # "Tout" → vider la sélection
            return {**store, "months": [], "weeks": []}
        if val in months:
            months.remove(val)
        else:
            months.append(val)
        return {**store, "months": months, "weeks": []}  # reset semaines si mois change

    if chip_type == "spotify-chip-week":
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
    Output("spotify-period-selector", "children"),
    Output("spotify-content",         "children"),
    Input("spotify-sel-store",        "data"),
)
def refresh_view(sel):
    sel      = sel or _DEFAULT_SEL
    df       = _load_spotify()
    filtered = _apply_filter(df, sel)
    return _period_selector(df, sel), _build_content(filtered, sel)
