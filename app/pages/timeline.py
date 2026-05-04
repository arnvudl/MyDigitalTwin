import os
import datetime
import calendar
import pandas as pd
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, callback, ALL
import dash_mantine_components as dmc
from dash_iconify import DashIconify
from app.icons import svg_icon, FOLDER
from dash.exceptions import PreventUpdate
from functools import lru_cache
from config import WAREHOUSE

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = WAREHOUSE

SOURCES = {
    # Existants
    "netflix_views":            {"date_col": "watch_date",  "label": "Netflix",          "color": "#E50914"},
    "spotify_streams":          {"date_col": "listen_ts",   "label": "Spotify",          "color": "#1DB954"},
    "google_searches":          {"date_col": "event_date",  "label": "Google",           "color": "#4285F4"},
    "youtube_watch":            {"date_col": "event_date",  "label": "YouTube",          "color": "#FF9900"},
    "twitter_tweets":           {"date_col": "event_date",  "label": "Twitter",          "color": "#1DA1F2"},
    # TikTok — 3 sources
    "tiktok_watch":             {"date_col": "event_date",  "label": "TikTok Watch",     "color": "#00F2EA"},
    "tiktok_likes":             {"date_col": "event_date",  "label": "TikTok Likes",     "color": "#FE2C55"},
    "tiktok_searches":          {"date_col": "event_date",  "label": "TikTok Search",    "color": "#2D2D2D"},
    # Instagram — 7 sources
    "instagram_likes":          {"date_col": "event_date",  "label": "IG Likes",         "color": "#E1306C"},
    "instagram_saved":          {"date_col": "event_date",  "label": "IG Sauvegardés",   "color": "#C13584"},
    "instagram_comments":       {"date_col": "event_date",  "label": "IG Commentaires",  "color": "#FCAF45"},
    "instagram_posts_viewed":   {"date_col": "event_date",  "label": "IG Posts vus",     "color": "#F56040"},
    "instagram_videos_watched": {"date_col": "event_date",  "label": "IG Vidéos",        "color": "#FFDC80"},
    "instagram_story_likes":    {"date_col": "event_date",  "label": "IG Stories",       "color": "#833AB4"},
    "instagram_searches":       {"date_col": "event_date",  "label": "IG Recherches",    "color": "#405DE6"},
}

COLOR_MAP  = {cfg["label"]: cfg["color"] for cfg in SOURCES.values()}
YEARS      = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
MONTHS_FR  = ["Janvier","Février","Mars","Avril","Mai","Juin",
              "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

_CHART_STYLE = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)",
    font_color="white", margin=dict(t=55, b=40, l=50, r=30),
    xaxis=dict(showgrid=False, title=""),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title=""),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
)

# ─── DATA ────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=32)
def load_year_data(year):
    all_events = []
    for table, cfg in SOURCES.items():
        table_path = os.path.join(DELTA_BASE, table)
        if not os.path.exists(table_path):
            continue
        try:
            files = [f for f in os.listdir(table_path) if f.endswith(".parquet")]
            for f in files:
                df = pd.read_parquet(os.path.join(table_path, f), columns=[cfg["date_col"]])
                col = pd.to_datetime(df[cfg["date_col"]], errors="coerce")
                if col.dt.tz is not None:
                    col = col.dt.tz_localize(None)
                df["event_date"] = col
                df = df[df["event_date"].dt.year == int(year)].copy()
                if not df.empty:
                    df["source"]  = cfg["label"]
                    df["month"]   = df["event_date"].dt.month
                    df["day"]     = df["event_date"].dt.day
                    df["hour"]    = df["event_date"].dt.hour
                    df["weekday"] = df["event_date"].dt.dayofweek
                    all_events.append(df[["event_date","source","month","day","hour","weekday"]])
        except:
            continue
    return pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()


def get_weeks_of_month(year, month):
    """Retourne les semaines (lun→dim) qui se chevauchent avec ce mois, en ordre."""
    _, n_days = calendar.monthrange(year, month)
    seen = {}
    for day in range(1, n_days + 1):
        d = datetime.date(year, month, day)
        monday = d - datetime.timedelta(days=d.weekday())
        key = monday.isoformat()
        if key not in seen:
            sunday    = monday + datetime.timedelta(days=6)
            d_start   = max(monday, datetime.date(year, month, 1))
            d_end     = min(sunday, datetime.date(year, month, n_days))
            seen[key] = {
                "start": monday.isoformat(),
                "end":   sunday.isoformat(),
                "disp":  f"{d_start.day}/{d_start.month} – {d_end.day}/{d_end.month}",
            }
    return list(seen.values())


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    return html.Div(className="page-wrapper", children=[
        dcc.Store(id="selected-year",  data=2025),
        dcc.Store(id="selected-month", data=None),
        dcc.Store(id="selected-week",  data=None),
        html.Div(className="home-container", children=[
            html.Div(id="timeline-header",
                     style={"width": "100%", "maxWidth": "1200px", "margin": "0 auto"}),
            html.Div(style={"width": "100%", "maxWidth": "1200px", "margin": "0 auto"},
                     children=[dcc.Loading(type="default", color="var(--violet-bright)",
                                           children=html.Div(id="timeline-main-content"))])
        ])
    ])


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
@callback(
    Output("selected-year",  "data"),
    Output("selected-month", "data", allow_duplicate=True),
    Output("selected-week",  "data", allow_duplicate=True),
    Input({"type": "year-filter", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def update_year(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate
    return int(ctx.triggered_id["index"]), None, None


@callback(
    Output("selected-month", "data"),
    Output("selected-week",  "data"),
    Input({"type": "month-card", "index": ALL}, "n_clicks"),
    Input({"type": "week-card",  "index": ALL}, "n_clicks"),
    Input({"type": "nav-btn",    "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_navigation(month_clicks, week_clicks, nav_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate
    tid = ctx.triggered_id
    t   = tid.get("type") if isinstance(tid, dict) else None

    if t == "month-card":
        return tid["index"], None
    if t == "week-card":
        return dash.no_update, tid["index"]
    if t == "nav-btn":
        if tid["index"] == "back-year":
            return None, None
        if tid["index"] == "back-month":
            return dash.no_update, None
    raise PreventUpdate


@callback(
    Output("timeline-header",       "children"),
    Output("timeline-main-content", "children"),
    Input("selected-year",  "data"),
    Input("selected-month", "data"),
    Input("selected-week",  "data"),
)
def render_page(year, month_idx, week_start_str):
    df = load_year_data(year)

    # ── YEAR VIEW ─────────────────────────────────────────────────────────
    if month_idx is None:
        header = html.Div(className="home-hero",
                          style={"textAlign": "center", "marginBottom": "60px"}, children=[
            dmc.Text("Chronologie numérique", className="home-hero-label"),
            dmc.Title([html.Em("Timeline"), f" {year}"], order=1, className="home-hero-title"),
            html.Div(className="filter-bar",
                     style={"marginTop": "30px", "display": "flex", "justifyContent": "center"},
                     children=[html.Div(className="filter-chips-row", children=[
                         html.Div(str(y), id={"type": "year-filter", "index": y},
                                  className=f"filter-chip {'filter-chip-active' if y == year else ''}")
                         for y in YEARS
                     ])])
        ])
        cards = []
        for i, name in enumerate(MONTHS_FR, 1):
            count = len(df[df["month"] == i]) if not df.empty else 0
            cards.append(html.Div(
                id={"type": "month-card", "index": i}, className="profile-card",
                style={"cursor": "pointer", "padding": "40px 20px", "textAlign": "center"},
                children=[
                    DashIconify(icon=FOLDER, width=56,
                                style={"color": "var(--text-secondary)", "marginBottom": "15px"}),
                    dmc.Text(name, className="profile-platform-name", fw=600,
                             style={"fontSize": "20px"}),
                    dmc.Text(f"{count:,} act.".replace(",", "\u202f"),
                             className="profile-count", c="dimmed", size="sm"),
                ]
            ))
        content = html.Div(className="clusters-grid",
                           style={"gridTemplateColumns": "repeat(4, 1fr)", "gap": "20px", "width": "100%"},
                           children=cards)
        return header, content

    month_name = MONTHS_FR[month_idx - 1]

    # ── MONTH VIEW (semaines) ──────────────────────────────────────────────
    if week_start_str is None:
        header = html.Div(className="home-hero",
                          style={"textAlign": "left", "marginBottom": "40px"}, children=[
            html.Div("← Retour", id={"type": "nav-btn", "index": "back-year"},
                     className="nav-back-link"),
            dmc.Title([html.Em(month_name), f" {year}"], order=1, className="home-hero-title"),
        ])

        df_m = df[df["month"] == month_idx].copy() if not df.empty else pd.DataFrame()
        weeks = get_weeks_of_month(year, month_idx)

        # Pastilles sources actives ce mois
        source_counts = (
            df_m.groupby("source").size().sort_values(ascending=False).head(8)
            if not df_m.empty else pd.Series(dtype=int)
        )
        pills = dmc.Group(
            gap="xs",
            style={"marginBottom": "28px"},
            children=[
                dmc.Badge(
                    f"{s}  {c:,}".replace(",", "\u202f"),
                    variant="light",
                    size="sm",
                    style={
                        "background": f"{COLOR_MAP.get(s,'#888')}18",
                        "color": COLOR_MAP.get(s, "#aaa"),
                        "border": f"1px solid {COLOR_MAP.get(s,'#aaa')}55",
                    },
                )
                for s, c in source_counts.items()
            ]
        )

        # Cartes de semaines
        week_cards = []
        for w in weeks:
            w_start_d = datetime.date.fromisoformat(w["start"])
            w_end_d   = datetime.date.fromisoformat(w["end"])
            if not df_m.empty:
                mask = (
                    (df_m["event_date"].dt.date >= w_start_d) &
                    (df_m["event_date"].dt.date <= w_end_d)
                )
                df_wk    = df_m[mask]
                count    = len(df_wk)
                top_srcs = (
                    df_wk.groupby("source").size()
                    .sort_values(ascending=False).head(5).index.tolist()
                    if count > 0 else []
                )
            else:
                count, top_srcs = 0, []

            week_cards.append(html.Div(
                id={"type": "week-card", "index": w["start"]},
                className="profile-card",
                style={"cursor": "pointer", "padding": "28px 20px", "textAlign": "center"},
                children=[
                    html.Div(w["disp"],
                             style={"fontSize": "0.85rem", "color": "var(--text-secondary)",
                                    "marginBottom": "8px", "fontWeight": "500"}),
                    html.Div(f"{count:,}".replace(",", "\u202f"),
                             className="profile-count", style={"fontSize": "1.8rem", "marginBottom": "12px"}),
                    html.Div(
                        style={"display": "flex", "justifyContent": "center", "gap": "6px"},
                        children=[
                            html.Span(style={
                                "width": "9px", "height": "9px", "borderRadius": "50%",
                                "background": COLOR_MAP.get(s, "#888"), "display": "inline-block"
                            })
                            for s in top_srcs
                        ]
                    ),
                ]
            ))

        content = html.Div([
            pills,
            html.Div(className="clusters-grid",
                     style={"gridTemplateColumns": "repeat(3, 1fr)", "gap": "20px", "width": "100%"},
                     children=week_cards),
        ])
        return header, content

    # ── WEEK VIEW (jour par jour) ──────────────────────────────────────────
    w_start = datetime.date.fromisoformat(week_start_str)
    w_end   = w_start + datetime.timedelta(days=6)
    label   = f"Semaine du {w_start.day}/{w_start.month} au {w_end.day}/{w_end.month}"

    header = html.Div(className="home-hero",
                      style={"textAlign": "left", "marginBottom": "40px"}, children=[
        html.Div("← Retour au mois", id={"type": "nav-btn", "index": "back-month"},
                 className="nav-back-link"),
        dmc.Title([html.Em(label)], order=1, className="home-hero-title"),
    ])

    if df.empty:
        return header, html.Div("Aucune donnée.", className="detail-panel",
                                style={"textAlign": "center"})

    df_w = df[
        (df["event_date"].dt.date >= w_start) &
        (df["event_date"].dt.date <= w_end)
    ].copy()

    if df_w.empty:
        return header, html.Div("Aucune activité cette semaine.", className="detail-panel",
                                style={"textAlign": "center"})

    df_w["date_only"] = df_w["event_date"].dt.date

    # Chart 1 : stacked bar par jour × source
    daily = df_w.groupby(["date_only", "source"]).size().reset_index(name="count")
    daily["date_only"] = pd.to_datetime(daily["date_only"])
    daily["day_label"] = daily["date_only"].dt.strftime("%a %d/%m")
    fig_daily = px.bar(
        daily, x="day_label", y="count", color="source",
        title="Activité jour par jour",
        color_discrete_map=COLOR_MAP, barmode="stack",
    )
    fig_daily.update_layout(**_CHART_STYLE)

    # Chart 2 : distribution horaire
    hourly = df_w.groupby("hour").size().reset_index(name="count")
    fig_hour = px.bar(
        hourly, x="hour", y="count", title="Intensité horaire",
        color="count", color_continuous_scale=["#4A00E0", "#00D2FF"],
    )
    fig_hour.update_layout(**{**_CHART_STYLE, "coloraxis_showscale": False})

    # Chart 3 : sources (horizontal bar)
    by_source = (
        df_w.groupby("source").size().reset_index(name="count")
        .sort_values("count", ascending=True)
    )
    fig_src = px.bar(
        by_source, x="count", y="source", orientation="h",
        title="Sources", color="source", color_discrete_map=COLOR_MAP,
    )
    fig_src.update_layout(**{**_CHART_STYLE, "showlegend": False,
                              "yaxis": {**_CHART_STYLE["yaxis"], "tickfont": {"size": 10}}})

    # Stat cards
    total      = len(df_w)
    day_counts = df_w.groupby("date_only").size()
    peak_day   = day_counts.idxmax()
    peak_str   = pd.Timestamp(peak_day).strftime("%a %d/%m")
    peak_hour  = int(hourly.loc[hourly["count"].idxmax(), "hour"]) if not hourly.empty else 0
    n_sources  = df_w["source"].nunique()

    stats = html.Div(
        style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)", "gap": "16px", "marginBottom": "30px"},
        children=[
            _stat_card(f"{total:,}".replace(",", "\u202f"), "activités", "var(--violet-bright)"),
            _stat_card(str(n_sources), "sources actives", "#1DB954"),
            _stat_card(peak_str,       "jour le plus actif", "#FF9900"),
            _stat_card(f"{peak_hour}h", "heure de pointe", "#E1306C"),
        ]
    )

    content = html.Div([
        stats,
        html.Div(className="clusters-grid",
                 style={"gridTemplateColumns": "1fr 1fr", "gap": "30px", "width": "100%"}, children=[
            dmc.Card(withBorder=True, radius="md", className="stat-card",
                     style={"gridColumn": "span 2", "height": "440px", "padding": "20px"},
                     children=[dcc.Graph(figure=fig_daily, responsive=True,
                                        style={"width": "100%", "height": "100%"})]),
            dmc.Card(withBorder=True, radius="md", className="stat-card",
                     style={"height": "340px", "padding": "20px"},
                     children=[dcc.Graph(figure=fig_hour, responsive=True,
                                        style={"width": "100%", "height": "100%"})]),
            dmc.Card(withBorder=True, radius="md", className="stat-card",
                     style={"height": "340px", "padding": "20px"},
                     children=[dcc.Graph(figure=fig_src, responsive=True,
                                        style={"width": "100%", "height": "100%"})]),
        ]),
    ])
    return header, content


def _stat_card(value, label, color):
    return html.Div(
        className="stat-card",
        style={"padding": "20px", "textAlign": "center"},
        children=[
            dmc.Text(value, fw=700, style={"fontSize": "1.9rem", "color": color}),
            dmc.Text(label, size="xs", c="dimmed", style={"marginTop": "4px"}),
        ]
    )
