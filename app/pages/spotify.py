import os
import pandas as pd
import plotly.graph_objects as go
from functools import lru_cache
from dash import ALL, Input, Output, State, callback, dcc, html, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify
from app.icons import svg_icon, MUSIC, CLOCK, MIC
from config import WAREHOUSE

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = WAREHOUSE

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


@lru_cache(maxsize=1)
def _load_playlists() -> pd.DataFrame:
    path = os.path.join(DELTA_BASE, "spotify_playlists")
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
            dfs.append(pd.read_parquet(f))
        except Exception:
            pass
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


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
    tout_active = len(active_vals) == 0
    return html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "8px", "flexWrap": "wrap"},
        children=[
            html.Span(f"{row_label} :", className="filter-row-label"),
            _chip("Tout", chip_type, None, tout_active),
            *[_chip(lbl, chip_type, val, val in active_vals) for val, lbl in items],
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
        parts.append(", ".join(month_labels[:3]) + (f" +{len(month_labels)-3}" if len(month_labels) > 3 else ""))
    if weeks:
        week_labels = [f"S{w}" for w in sorted(weeks)]
        parts.append(", ".join(week_labels[:4]) + (f" +{len(week_labels)-4}" if len(week_labels) > 4 else ""))
    return " · ".join(parts)


def _period_selector(df: pd.DataFrame, sel: dict) -> html.Div:
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []

    rows = [_chip_row(
        "Année", "spotify-chip-year",
        [(y, str(y)) for y in _years(df)],
        [year] if year else [],
    )]

    if year is not None:
        rows.append(_chip_row(
            "Mois", "spotify-chip-month",
            [(m, MONTH_NAMES[m]) for m in _months_for_year(df, year)],
            months,
        ))

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


# ─── SPOTIFY API / CACHE ──────────────────────────────────────────────────────
from app.spotify_utils import spotify_meta


def _get_playlist_cover(playlist_name: str, tracks_df: pd.DataFrame) -> str | None:
    """Use first track's album art as playlist cover (cached via spotify_meta)."""
    cache_key = f"playlist_cover:{playlist_name}"
    if cache_key in spotify_meta.cache:
        return spotify_meta.cache[cache_key]

    if tracks_df.empty:
        return None

    # Try up to 3 tracks to find one with an image
    for _, row in tracks_df.head(3).iterrows():
        img = spotify_meta.get_track_image(row.get("trackName"), row.get("artistName"))
        if img:
            spotify_meta.cache[cache_key] = img
            spotify_meta._save_cache()
            return img

    spotify_meta.cache[cache_key] = None
    spotify_meta._save_cache()
    return None


# ─── PLAYLISTS SIDEBAR ───────────────────────────────────────────────────────────
def _build_playlists_sidebar(playlists_df: pd.DataFrame, selected_playlist: str | None) -> html.Div:
    if playlists_df.empty:
        return html.Div()

    summary = (
        playlists_df.groupby("playlistName")
        .agg(track_count=("trackName", "count"))
        .reset_index()
        .sort_values("track_count", ascending=False)
    )

    cards = []
    for _, row in summary.iterrows():
        name = row["playlistName"]
        count = row["track_count"]
        tracks = playlists_df[playlists_df["playlistName"] == name]
        img_url = _get_playlist_cover(name, tracks)

        is_active = name == selected_playlist

        cards.append(
            html.Div(
                id={"type": "spotify-playlist-card", "index": name},
                n_clicks=0,
                className=f"spotify-playlist-card {'spotify-playlist-card-active' if is_active else ''}",
                children=[
                    html.Img(
                        src=img_url or "https://via.placeholder.com/64?text=♪",
                        style={"width": "48px", "height": "48px", "borderRadius": "4px", "objectFit": "cover"},
                    ),
                    html.Div(
                        style={"flex": "1", "minWidth": "0"},
                        children=[
                            html.Div(name, style={
                                "fontSize": "14px", "fontWeight": "600", "color": "#fff",
                                "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis",
                            }),
                            html.Div(f"{count} titres", style={"fontSize": "12px", "color": "var(--text-muted)", "marginTop": "2px"}),
                        ],
                    ),
                ],
            )
        )

    return html.Div(
        className="spotify-sidebar",
        children=[
            # Header style "Ma Bibliothèque" Spotify
            html.Div(
                className="spotify-library-header",
                children=[
                    dmc.Group(gap="xs", align="center", children=[
                        DashIconify(icon="tabler:library", width=20, color="rgba(255,255,255,0.7)"),
                        dmc.Text("Ma Bibliothèque", fw=700, size="sm", c="dimmed"),
                    ]),
                    dmc.Badge(str(len(cards)), variant="light", color="gray", size="xs", radius="xl"),
                ],
            ),
            html.Div(
                style={"display": "flex", "flexDirection": "column", "gap": "2px"},
                children=cards,
            ),
        ],
    )


# ─── PLAYLIST DETAIL ─────────────────────────────────────────────────────────
def _build_playlist_detail(playlists_df: pd.DataFrame, playlist_name: str) -> list:
    tracks = playlists_df[playlists_df["playlistName"] == playlist_name].copy()

    if tracks.empty:
        return [html.P("Playlist introuvable.", style={"color": "var(--text-muted)"})]

    img_url = _get_playlist_cover(playlist_name, tracks)
    track_count = len(tracks)

    cover = (
        html.Img(src=img_url, style={"width": "120px", "height": "120px", "objectFit": "cover", "borderRadius": "8px"})
        if img_url
        else html.Div(
            svg_icon(MUSIC, size="40"),
            style={
                "width": "120px", "height": "120px", "background": "#282828",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "color": "#555", "borderRadius": "8px",
            },
        )
    )

    # Tracklist rows
    track_rows = []
    for i, (_, t) in enumerate(tracks.iterrows(), 1):
        track_rows.append(
            html.Div(
                style={
                    "display": "flex", "alignItems": "center", "padding": "8px 12px",
                    "borderRadius": "6px", "gap": "14px",
                },
                className="playlist-row",
                children=[
                    html.Span(str(i), style={"width": "24px", "color": "var(--text-muted)", "fontSize": "13px", "textAlign": "right", "flexShrink": "0"}),
                    html.Div(style={"flex": "1", "minWidth": "0"}, children=[
                        html.Div(t.get("trackName", "—"), style={
                            "fontSize": "14px", "fontWeight": "500", "color": "#fff",
                            "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis",
                        }),
                        html.Div(t.get("artistName", ""), style={"fontSize": "12px", "color": "var(--text-muted)"}),
                    ]),
                    html.Div(t.get("albumName", ""), style={
                        "fontSize": "12px", "color": "var(--text-muted)",
                        "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis",
                        "maxWidth": "180px",
                    }),
                ],
            )
        )

    return [
        # Header
        dmc.Group(
            gap="xl",
            align="flex-end",
            style={"marginBottom": "32px"},
            children=[
                cover,
                dmc.Stack(
                    gap="xs",
                    children=[
                        dmc.Badge("Playlist", color="green", variant="light",
                                  style={"letterSpacing": "2px", "textTransform": "uppercase"}),
                        dmc.Title(playlist_name, order=2, style={"fontFamily": "var(--font-serif)"}),
                        dmc.Text(f"{track_count} titres", c="dimmed", size="sm"),
                    ],
                ),
            ],
        ),
        # Tracklist header
        html.Div(
            style={"display": "flex", "padding": "0 12px 10px", "borderBottom": f"1px solid rgba(255,255,255,0.08)", "marginBottom": "8px"},
            children=[
                html.Span("#", style={"width": "24px", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase", "textAlign": "right"}),
                html.Span("Titre", style={"flex": "1", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase", "marginLeft": "14px"}),
                html.Span("Album", style={"fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase", "maxWidth": "180px", "width": "180px"}),
            ],
        ),
        html.Div(
            style={"background": "rgba(0,0,0,0.2)", "borderRadius": "8px", "padding": "4px 0"},
            children=track_rows,
        ),
    ]


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

    cards = []
    for _, row in top.iterrows():
        img_url = spotify_meta.get_artist_image(row["artistName"])

        img_component = (
            html.Img(src=img_url, style={"width": "100%", "height": "100%", "objectFit": "cover"})
            if img_url
            else html.Div(
                svg_icon(MIC, size="32"),
                style={"display": "flex", "alignItems": "center", "justifyContent": "center",
                       "width": "100%", "height": "100%", "color": "#888",
                       "background": "linear-gradient(135deg, #282828, #121212)"},
            )
        )

        cards.append(html.Div(
            style={"display": "flex", "flexDirection": "column", "alignItems": "center",
                   "width": "120px", "gap": "10px", "textAlign": "center"},
            children=[
                html.Div(
                    style={"width": "100px", "height": "100px", "borderRadius": "50%",
                           "overflow": "hidden", "boxShadow": "0 8px 24px rgba(0,0,0,0.3)",
                           "background": "#282828", "border": "1px solid rgba(255,255,255,0.1)"},
                    children=[img_component],
                ),
                html.Div([
                    html.Div(row["artistName"], style={
                        "fontSize": "13px", "fontWeight": "600", "color": "white",
                        "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis", "width": "110px",
                    }),
                    html.Div(f"{row['streams']} streams", style={"fontSize": "11px", "color": SPOTIFY_GREEN}),
                ]),
            ],
        ))

    return html.Div(
        style={"display": "flex", "gap": "20px", "flexWrap": "wrap", "justifyContent": "center", "padding": "20px 0"},
        children=cards,
    )


def _render_top_tracks_visual(df: pd.DataFrame, n: int = 12) -> html.Div:
    if df.empty:
        return html.Div()

    top = (
        df.groupby(["trackName", "artistName"])
        .agg(streams=("msPlayed", "count"), minutes=("minutes_played", "sum"))
        .reset_index().sort_values("streams", ascending=False).head(n)
    )

    rows = []
    for i, (_, row) in enumerate(top.iterrows()):
        img_url = spotify_meta.get_track_image(row["trackName"], row["artistName"])
        rows.append(html.Div(
            style={
                "display": "flex", "alignItems": "center", "padding": "8px 12px",
                "borderRadius": "8px", "gap": "16px", "cursor": "default",
            },
            className="playlist-row",
            children=[
                html.Span(str(i + 1), style={"width": "20px", "color": "var(--text-muted)", "fontSize": "13px"}),
                html.Img(
                    src=img_url or "https://via.placeholder.com/40?text=♪",
                    style={"width": "40px", "height": "40px", "borderRadius": "4px"},
                ),
                html.Div(style={"flex": "1", "minWidth": "0"}, children=[
                    html.Div(row["trackName"], style={
                        "fontSize": "14px", "fontWeight": "500", "color": "white",
                        "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis",
                    }),
                    html.Div(row["artistName"], style={"fontSize": "12px", "color": "var(--text-muted)"}),
                ]),
                html.Div(f"{row['streams']} plays", style={"fontSize": "12px", "color": "var(--text-muted)", "width": "70px", "textAlign": "right"}),
                html.Div(f"{int(row['minutes'])}m", style={"fontSize": "12px", "color": "var(--text-muted)", "width": "45px", "textAlign": "right"}),
            ],
        ))

    return html.Div(
        style={"display": "flex", "flexDirection": "column", "gap": "4px",
               "background": "rgba(0,0,0,0.2)", "borderRadius": "12px", "padding": "12px"},
        children=[
            html.Div(
                style={"display": "flex", "padding": "0 12px 8px",
                       "borderBottom": "1px solid rgba(255,255,255,0.05)", "marginBottom": "8px"},
                children=[
                    html.Span("#", style={"width": "20px", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase"}),
                    html.Span("", style={"width": "40px", "marginLeft": "16px"}),
                    html.Span("Titre", style={"flex": "1", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase"}),
                    html.Span("Écoutes", style={"width": "70px", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase", "textAlign": "right"}),
                    html.Span("Durée", style={"width": "45px", "fontSize": "11px", "color": "var(--text-muted)", "textTransform": "uppercase", "textAlign": "right"}),
                ],
            ),
            *rows,
        ],
    )


def _chart_activity(df: pd.DataFrame, sel: dict) -> go.Figure:
    if df.empty:
        return go.Figure()
    year   = sel.get("year")
    months = sel.get("months") or []
    weeks  = sel.get("weeks")  or []

    if year and weeks:
        grouped = df.groupby("listen_week").agg(streams=("trackName", "count")).reset_index().sort_values("listen_week")
        x_vals  = grouped["listen_week"].apply(lambda w: f"S{w}")
        title   = "Écoutes par semaine"
    elif year and months:
        grouped = df.groupby("month_int").agg(streams=("trackName", "count")).reset_index().sort_values("month_int")
        x_vals  = grouped["month_int"].map(MONTH_NAMES)
        title   = "Écoutes par mois sélectionnés"
    elif year:
        grouped = df.groupby("listen_month").agg(streams=("trackName", "count")).reset_index().sort_values("listen_month")
        x_vals  = grouped["listen_month"]
        title   = f"Écoutes par mois — {year}"
    else:
        grouped = df.groupby("listen_month").agg(streams=("trackName", "count")).reset_index().sort_values("listen_month")
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
def _build_main_content(df: pd.DataFrame, sel: dict) -> list:
    if df.empty:
        return [html.P("Aucune donnée d'écoute pour cette période.",
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
        # Stats
        html.Div(className="stats-row", style={"marginBottom": "24px"}, children=[
            _stat(DashIconify(icon=MUSIC, width=22), f"{total_streams:,}", "Streams"),
            _stat(DashIconify(icon=CLOCK, width=22), f"{total_hours:,}h",  "Écoutées"),
            _stat(DashIconify(icon=MIC,   width=22), f"{n_artists:,}",     "Artistes"),
            _stat(DashIconify(icon=MUSIC, width=22), f"{n_tracks:,}",      "Titres distincts"),
        ]),

        # Top artistes
        dmc.Card(
            withBorder=True,
            radius="md",
            className="data-panel",
            style={"marginBottom": "24px"},
            children=[
                dmc.Text("Top Artistes", fw=700, size="xs",
                         style={"color": SPOTIFY_GREEN, "textTransform": "uppercase",
                                "letterSpacing": "2px", "marginBottom": "16px"}),
                _render_top_artists_visual(df),
            ],
        ),

        # Top titres
        dmc.Card(
            withBorder=True,
            radius="md",
            className="data-panel",
            style={"marginBottom": "24px"},
            children=[
                dmc.Text("Top Titres", fw=700, size="xs",
                         style={"color": SPOTIFY_GREEN, "textTransform": "uppercase",
                                "letterSpacing": "2px", "marginBottom": "16px"}),
                _render_top_tracks_visual(df, n=12),
            ],
        ),

        # Graphiques
        dmc.SimpleGrid(
            cols={"base": 1, "md": 2},
            spacing="md",
            children=[
                dmc.Card(withBorder=True, radius="md", className="data-panel",
                         style={"flex": "1.5"},
                         children=[dcc.Graph(figure=_chart_activity(df, sel), config={"displayModeBar": False})]),
                dmc.Card(withBorder=True, radius="md", className="data-panel",
                         children=[dcc.Graph(figure=_chart_hourly(df), config={"displayModeBar": False})]),
            ],
        ),
    ]


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    df           = _load_spotify()
    playlists_df = _load_playlists()

    if df.empty and playlists_df.empty:
        return html.Div(className="page-wrapper", children=[
            html.Div(className="page-empty-state", children=[
                DashIconify(icon=MUSIC, width=56, style={"color": "var(--text-secondary)"}),
                dmc.Title("Spotify", order=2),
                dmc.Text("Lance d'abord 01_exploration/spotify.ipynb.", c="dimmed", size="sm"),
            ])
        ])

    return html.Div(className="page-wrapper", children=[
        html.Div(
            className="spotify-layout",
            children=[
                # Sidebar
                html.Div(
                    id="spotify-sidebar-container",
                    className="spotify-sidebar-container",
                    children=_build_playlists_sidebar(playlists_df, None)
                ),

                # Main Content
                html.Div(
                    className="spotify-main-content",
                    children=[
                        # Header
                        html.Div(id="spotify-hero", children=[
                            html.Div(className="home-hero", style={"textAlign": "center"}, children=[
                                dmc.Text("Wrapped Custom • Année · Mois · Semaine",
                                         className="home-hero-label",
                                         style={"color": SPOTIFY_GREEN}),
                                dmc.Title(
                                    html.Span(["Mon ", html.Em("Spotify")]),
                                    order=1,
                                    className="home-hero-title",
                                    style={"fontSize": "56px"},
                                ),
                                dmc.Text("Tes playlists et tes écoutes en un coup d'œil.",
                                         className="home-hero-sub", c="dimmed"),
                            ]),
                        ]),

                        # Back button (visible only in playlist detail)
                        html.Button(
                            "← Dashboard",
                            id="spotify-back-btn",
                            n_clicks=0,
                            style={"display": "none"},
                            className="spotify-back-btn",
                        ),

                        dcc.Store(id="spotify-sel-store", data=_DEFAULT_SEL),
                        dcc.Store(id="spotify-playlist-store", data=None),

                        html.Div(id="spotify-period-selector",
                                 children=_period_selector(df, _DEFAULT_SEL)),

                        html.Div(id="spotify-content"),
                    ],
                ),
            ],
        )
    ])


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
@callback(
    Output("spotify-sel-store", "data"),
    Input({"type": "spotify-chip-year",  "index": ALL}, "n_clicks"),
    Input({"type": "spotify-chip-month", "index": ALL}, "n_clicks"),
    Input({"type": "spotify-chip-week",  "index": ALL}, "n_clicks"),
    State("spotify-sel-store", "data"),
    prevent_initial_call=True,
)
def update_selection(clicks_y, clicks_m, clicks_w, store):
    from dash import ctx
    store = store or _DEFAULT_SEL

    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
        return store

    chip_type = ctx.triggered_id.get("type", "")
    index     = ctx.triggered_id.get("index", "__all__")
    val       = None if index == "__all__" else int(index)

    if chip_type == "spotify-chip-year":
        new_year = None if (val == store.get("year")) else val
        return {"year": new_year, "months": [], "weeks": []}

    if chip_type == "spotify-chip-month":
        months = list(store.get("months") or [])
        if val is None:
            return {**store, "months": [], "weeks": []}
        if val in months:
            months.remove(val)
        else:
            months.append(val)
        return {**store, "months": months, "weeks": []}

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
    Output("spotify-playlist-store", "data"),
    Input({"type": "spotify-playlist-card", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_playlist(clicks):
    from dash import ctx
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
        return no_update
    if not any(c > 0 for c in (clicks or [])):
        return no_update
    return ctx.triggered_id["index"]


@callback(
    Output("spotify-playlist-store", "data", allow_duplicate=True),
    Input("spotify-back-btn", "n_clicks"),
    prevent_initial_call=True,
)
def go_back(n):
    if n:
        return None
    return no_update


@callback(
    Output("spotify-period-selector", "children"),
    Output("spotify-period-selector", "style"),
    Output("spotify-content",         "children"),
    Output("spotify-back-btn",        "style"),
    Output("spotify-hero",            "style"),
    Output("spotify-sidebar-container", "children"),
    Input("spotify-sel-store",        "data"),
    Input("spotify-playlist-store",   "data"),
)
def refresh_view(sel, selected_playlist):
    sel          = sel or _DEFAULT_SEL
    df           = _load_spotify()
    playlists_df = _load_playlists()
    filtered     = _apply_filter(df, sel)

    sidebar = _build_playlists_sidebar(playlists_df, selected_playlist)

    if selected_playlist:
        content       = _build_playlist_detail(playlists_df, selected_playlist)
        period_sel    = html.Div()
        period_style  = {"display": "none"}
        back_style    = {"display": "inline-block"}
        hero_style    = {"display": "none"}
    else:
        content       = _build_main_content(filtered, sel)
        period_sel    = _period_selector(df, sel)
        period_style  = {}
        back_style    = {"display": "none"}
        hero_style    = {}

    return period_sel, period_style, content, back_style, hero_style, sidebar
