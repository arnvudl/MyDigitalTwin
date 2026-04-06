import os
import pandas as pd
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, callback, dcc, html

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = "/app/warehouse" if os.path.exists("/app/warehouse") else "warehouse"

NETFLIX_RED = "#e50914"

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
        html.Div(className="stats-row", style={"marginBottom": "0"}, children=[
            _stat("🎬", f"{total:,}",    "Épisodes / Films"),
            _stat("📺", f"{n_series:,}", "Séries distinctes"),
            _stat("🎥", f"{n_movies:,}", "Films regardés"),
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
                    html.Div("🎬", style={"fontSize": "56px"}),
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
                html.Div(className="home-hero", children=[
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
            ],
        )
    ])


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
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
