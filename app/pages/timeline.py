import os
import pandas as pd
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, callback, State, ALL
from dash.exceptions import PreventUpdate
from functools import lru_cache

# ─── CONFIG ──────────────────────────────────────────────────────────────────
if os.path.exists("/app/warehouse"):
    DELTA_BASE = "/app/warehouse"
else:
    DELTA_BASE = "warehouse"

SOURCES = {
    "netflix_views": {"date_col": "watch_date", "label": "Netflix", "color": "#FF0000"},
    "spotify_streams": {"date_col": "listen_ts", "label": "Spotify", "color": "#1DB954"},
    "google_searches": {"date_col": "event_date", "label": "Google", "color": "#4285F4"},
    "youtube_watch": {"date_col": "event_date", "label": "YouTube", "color": "#FF9900"},
    "tiktok_watch": {"date_col": "event_date", "label": "TikTok", "color": "#00F2EA"},
    "instagram_likes": {"date_col": "event_date", "label": "Instagram", "color": "#E1306C"},
    "twitter_tweets": {"date_col": "event_date", "label": "Twitter", "color": "#1DA1F2"},
}

YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

# ─── DATA LOADING ────────────────────────────────────────────────────────────
@lru_cache(maxsize=32)
def load_year_data(year):
    all_events = []
    for table, cfg in SOURCES.items():
        table_path = os.path.join(DELTA_BASE, table)
        if not os.path.exists(table_path): continue
        try:
            files = [f for f in os.listdir(table_path) if f.endswith(".parquet")]
            for f in files:
                df = pd.read_parquet(os.path.join(table_path, f), columns=[cfg["date_col"]])
                df["event_date"] = pd.to_datetime(df[cfg["date_col"]])
                df = df[df["event_date"].dt.year == int(year)].copy()
                if not df.empty:
                    df["source"] = cfg["label"]
                    df["month"] = df["event_date"].dt.month
                    df["day"] = df["event_date"].dt.day
                    df["hour"] = df["event_date"].dt.hour
                    df["weekday"] = df["event_date"].dt.dayofweek
                    all_events.append(df[["event_date", "source", "month", "day", "hour", "weekday"]])
        except: continue
    return pd.concat(all_events) if all_events else pd.DataFrame()

# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    return html.Div(className="page-wrapper", children=[
        dcc.Store(id="selected-year", data=2025),
        dcc.Store(id="selected-month", data=None),
        
        html.Div(className="home-container", children=[
            # Header
            html.Div(id="timeline-header", style={"width": "100%", "maxWidth": "1200px", "margin": "0 auto"}),

            # Contenu principal
            html.Div(style={"width": "100%", "maxWidth": "1200px", "margin": "0 auto"}, children=[
                dcc.Loading(
                    type="default", color="var(--violet-bright)",
                    children=html.Div(id="timeline-main-content")
                )
            ])
        ])
    ])

# ─── CALLBACKS ───────────────────────────────────────────────────────────────

@callback(
    Output("selected-year", "data"),
    Output("selected-month", "data", allow_duplicate=True),
    Input({"type": "year-filter", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def update_year(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered: raise PreventUpdate
    new_year = int(ctx.triggered_id["index"])
    return new_year, None

@callback(
    Output("selected-month", "data"),
    Input({"type": "month-card", "index": ALL}, "n_clicks"),
    Input({"type": "nav-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def handle_navigation(card_clicks, nav_clicks):
    ctx = dash.callback_context
    if not ctx.triggered: return dash.no_update
    trigger_id = ctx.triggered_id
    if trigger_id.get("type") == "nav-btn": return None
    return trigger_id.get("index")

@callback(
    [Output("timeline-header", "children"), Output("timeline-main-content", "children")],
    [Input("selected-year", "data"), Input("selected-month", "data")]
)
def render_page(year, month_idx):
    months_names = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    
    # ─── 1. HEADER ───
    if month_idx is None:
        header = html.Div(className="home-hero", style={"textAlign": "center", "marginBottom": "60px"}, children=[
            html.Div("Chronologie numérique", className="home-hero-label"),
            html.H1([html.Em("Timeline"), f" {year}"], className="home-hero-title"),
            html.Div(className="filter-bar", style={"marginTop": "30px", "display": "flex", "justifyContent": "center"}, children=[
                html.Div(className="filter-chips-row", children=[
                    html.Div(str(y), id={"type": "year-filter", "index": y},
                             className=f"filter-chip {'filter-chip-active' if y == year else ''}") for y in YEARS
                ])
            ])
        ])
    else:
        header = html.Div(className="home-hero", style={"textAlign": "left", "marginBottom": "40px"}, children=[
            html.Div("← Retour à la grille", id={"type": "nav-btn", "index": "back"},
                     style={"cursor": "pointer", "color": "var(--violet-bright)", "marginBottom": "20px", "fontWeight": "600", "display": "inline-block"}),
            html.H1([html.Em(months_names[month_idx-1]), f" {year}"], className="home-hero-title"),
        ])

    df = load_year_data(year)
    
    if month_idx is None:
        # VUE GRILLE
        cards = []
        for i, name in enumerate(months_names, 1):
            count = len(df[df["month"] == i]) if not df.empty else 0
            cards.append(html.Div(
                id={"type": "month-card", "index": i}, className="profile-card",
                style={"cursor": "pointer", "padding": "40px 20px", "textAlign": "center"},
                children=[
                    html.Div("📂", style={"fontSize": "56px", "marginBottom": "15px"}),
                    html.Div(name, className="profile-platform-name", style={"fontSize": "20px"}),
                    html.Div(f"{count:,} act.".replace(',', ' '), className="profile-count")
                ]
            ))
        content = html.Div(className="clusters-grid", style={
            "gridTemplateColumns": "repeat(4, 1fr)", 
            "gap": "20px", 
            "width": "100%"
        }, children=cards)
    else:
        # VUE DÉTAIL
        df_m = df[df["month"] == month_idx].copy()
        if df_m.empty: return header, html.Div("Aucune donnée.", className="detail-panel", style={"textAlign": "center"})

        # Graphiques
        daily = df_m.groupby(['day', 'source']).size().reset_index(name='count')
        fig_line = px.line(daily, x="day", y="count", color="source", line_shape="spline",
                           title="Volume quotidien", color_discrete_map={cfg["label"]: cfg["color"] for cfg in SOURCES.values()})
        
        hourly = df_m.groupby('hour').size().reset_index(name='count')
        fig_hour = px.bar(hourly, x="hour", y="count", title="Intensité horaire",
                          color="count", color_continuous_scale=["#4A00E0", "#00D2FF"])
        
        wd_map = {0:'Lun', 1:'Mar', 2:'Mer', 3:'Jeu', 4:'Ven', 5:'Sam', 6:'Dim'}
        df_m['wd_name'] = df_m['weekday'].map(wd_map)
        weekly = df_m.groupby(['weekday', 'wd_name']).size().reset_index(name='count').sort_values('weekday')
        fig_week = px.bar(weekly, x="wd_name", y="count", title="Activité / Jour", color_discrete_sequence=["var(--violet-bright)"])

        for f in [fig_line, fig_hour, fig_week]:
            f.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.02)", font_color="white",
                            margin=dict(t=60, b=40, l=50, r=30), xaxis=dict(showgrid=False, title=""), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title=""))
            if f == fig_hour: f.update_layout(coloraxis_showscale=False)

        content = html.Div(className="clusters-grid", style={"gridTemplateColumns": "1fr 1fr", "gap": "30px", "width": "100%"}, children=[
            html.Div(className="stat-card", style={"gridColumn": "span 2", "height": "450px", "padding": "20px"}, children=[dcc.Graph(figure=fig_line, responsive=True, style={"width": "100%", "height": "100%"})]),
            html.Div(className="stat-card", style={"height": "350px", "padding": "20px"}, children=[dcc.Graph(figure=fig_hour, responsive=True, style={"width": "100%", "height": "100%"})]),
            html.Div(className="stat-card", style={"height": "350px", "padding": "20px"}, children=[dcc.Graph(figure=fig_week, responsive=True, style={"width": "100%", "height": "100%"})])
        ])

    return header, content
