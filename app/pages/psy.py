"""
Page /psy — Le Miroir
Wizard 4 étapes → génération d'un package ZIP "Dossier Clinique Numérique"
"""

import base64
import os
import sys
import tempfile
from datetime import datetime

import pandas as pd
from dash import Input, Output, State, callback, dcc, html, no_update, ALL
from config import WAREHOUSE

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = WAREHOUSE

from app.icons import svg_icon, CHAT, SEARCH, MUSIC
_svg_chat   = svg_icon(CHAT)
_svg_search = svg_icon(SEARCH)
_svg_music  = svg_icon(MUSIC)
SOURCES_OPTIONS = [
    {"id": "verbe",       "label": "Le Verbe",      "desc": "Messages TikTok + Instagram",           "icon": _svg_chat},
    {"id": "inconscient", "label": "L'Inconscient",  "desc": "Recherches Google & YouTube",           "icon": _svg_search},
    {"id": "emotionnel",  "label": "L'Émotionnel",   "desc": "Spotify, Netflix, TikTok Watch",        "icon": _svg_music},
]


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _data_volume(source_id: str) -> int:
    """Retourne le nombre de lignes disponibles pour une source."""
    mapping = {
        "verbe":       "tiktok_messages_text",
        "inconscient": "google_searches",
        "emotionnel":  "spotify_streams",
    }
    table = mapping.get(source_id)
    if not table:
        return 0
    path = os.path.join(DELTA_BASE, table)
    if not os.path.exists(path):
        return 0
    files = [f for f in os.listdir(path) if f.endswith(".parquet")]
    if not files:
        return 0
    try:
        df = pd.concat([pd.read_parquet(os.path.join(path, f)) for f in files], ignore_index=True)
        return len(df)
    except Exception:
        return 0


def _step_indicator(n: int, label: str, current: int) -> html.Div:
    status = "active" if n == current else ("done" if n < current else "pending")
    return html.Div(
        className=f"psy-step-item {status}",
        children=[
            html.Div(str(n), className="psy-step-number"),
            html.Span(label, className="psy-step-label"),
        ]
    )


def _step_separator() -> html.Div:
    return html.Div(className="psy-step-separator")


# ─── STEP LAYOUTS ────────────────────────────────────────────────────────────

def _step1_layout(start_date, end_date) -> html.Div:
    s = start_date or "2024-01-01"
    e = end_date or datetime.now().strftime("%Y-%m-%d")
    return html.Div([
        html.H3("Cadre Temporel", className="psy-section-title"),
        html.P("Sélectionne la période à analyser pour ton dossier.", className="psy-section-desc"),
        html.Div(className="psy-date-row", children=[
            html.Div([
                html.Label("Début", className="filter-label"),
                dcc.DatePickerSingle(
                    id="psy-date-start",
                    date=s,
                    display_format="DD/MM/YYYY",
                    first_day_of_week=1,
                    className="psy-datepicker",
                ),
            ], className="psy-date-field"),
            html.Span("→", className="psy-date-arrow"),
            html.Div([
                html.Label("Fin", className="filter-label"),
                dcc.DatePickerSingle(
                    id="psy-date-end",
                    date=e,
                    display_format="DD/MM/YYYY",
                    first_day_of_week=1,
                    className="psy-datepicker",
                ),
            ], className="psy-date-field"),
        ]),
        html.Div(id="psy-volume-preview", className="psy-volume-preview"),
    ])


def _step2_layout(selected_sources=None) -> html.Div:
    if selected_sources is None:
        selected_sources = ["verbe", "inconscient", "emotionnel"]

    instagram_notice = html.Div(
        style={
            "background": "rgba(124,90,246,0.07)",
            "border": "1px solid rgba(124,90,246,0.25)",
            "borderRadius": "10px", "padding": "12px 16px",
            "fontSize": "12px", "color": "rgba(255,255,255,0.55)",
            "marginBottom": "14px", "lineHeight": "1.6",
        },
        children=[
            html.Span("Instagram — ", style={"color": "#7c5af6", "fontWeight": "700"}),
            "Pour inclure tes conversations Instagram complètes, exporte-les depuis le dashboard Instagram "
            "(Settings → Privacy → Download Your Information). Place les fichiers JSON dans ",
            html.Code("data/Analyse comportementaliste/", style={"fontSize": "11px", "color": "#7c5af6"}),
            " avant de générer.",
        ],
    )

    source_cards = []
    for src in SOURCES_OPTIONS:
        vol = _data_volume(src["id"])
        is_selected = src["id"] in selected_sources
        source_cards.append(
            html.Div(
                id={"type": "psy-src-card", "index": src["id"]},
                n_clicks=0,
                className=f"psy-src-card {'selected' if is_selected else ''}",
                children=[
                    html.Span(src["icon"], className="psy-src-icon"),
                    html.Div(className="psy-src-info", children=[
                        html.Div(src["label"], className="psy-src-label"),
                        html.Div(src["desc"], className="psy-src-desc"),
                        html.Div(f"{vol:,} entrées disponibles", className="psy-src-vol") if vol > 0 
                        else html.Div("Aucune donnée", className="psy-src-empty"),
                    ]),
                    html.Div(
                        "✓" if is_selected else "+",
                        style={
                            "color": "#7c5af6" if is_selected else "rgba(255,255,255,0.2)",
                            "fontWeight": "800", "fontSize": "18px"
                        }
                    )
                ]
            )
        )
    return html.Div([
        html.H3("Choix des Sources", className="psy-section-title"),
        html.P("Clique pour sélectionner les dimensions de ta vie numérique à inclure.", className="psy-section-desc"),
        instagram_notice,
        html.Div(source_cards, className="psy-source-list"),
    ])


def _step3_layout(anon_value) -> html.Div:
    option_style = {
        "display": "flex", "alignItems": "center", "gap": "12px",
        "padding": "16px 20px", "borderRadius": "14px",
        "border": "1px solid rgba(255,255,255,0.08)",
        "background": "rgba(255,255,255,0.03)",
        "cursor": "pointer",
    }
    return html.Div([
        html.H3("Filtre de Confidentialité", className="psy-section-title"),
        html.P("Tes données restent chez toi. Ce filtre aide à l'anonymisation.", className="psy-section-desc"),
        html.Div([
            html.Div(style=option_style, children=[
                dcc.Checklist(
                    id="psy-anon-names",
                    options=[{"label": "", "value": "anon"}],
                    value=anon_value if anon_value is not None else ["anon"],
                    inputStyle={"width": "20px", "height": "20px", "accentColor": "#7c5af6"}
                ),
                html.Div([
                    html.Div("Remplacer les prénoms", className="psy-src-label"),
                    html.Div("Les prénoms détectés sont remplacés par [PRÉNOM] pour plus de discrétion.",
                             className="psy-src-desc"),
                ]),
            ]),
        ], style={"display": "flex", "flexDirection": "column", "gap": "10px"}),
    ])


def _step4_layout() -> html.Div:
    return html.Div([
        html.H3("Génération du Dossier", className="psy-section-title"),
        html.P("Prêt pour l'analyse. Le dossier sera téléchargé directement sur ton ordinateur.", className="psy-section-desc"),
        html.Div(id="psy-generate-result"),
        html.Button(
            children=["Générer et Télécharger"],
            id="psy-generate-btn",
            n_clicks=0,
            className="psy-generate-btn"
        ),
        dcc.Download(id="psy-download"),
    ])


# ─── MAIN LAYOUT ─────────────────────────────────────────────────────────────

def layout() -> html.Div:
    steps = ["Période", "Sources", "Confidentialité", "Génération"]
    now = datetime.now().strftime("%Y-%m-%d")
    return html.Div(
        className="psy-container",
        children=[
            # Header
            html.Div(className="psy-header", children=[
                html.Div("Analyse Comportementale", className="psy-label"),
                html.H1("Dossier Comportemental Numérique", className="psy-title"),
                html.P(
                    "Génère un package structuré pour analyser tes patterns numériques avec un LLM.",
                    className="psy-subtitle",
                ),
                html.Div(
                    style={
                        "background": "rgba(255,255,255,0.04)",
                        "border": "1px solid rgba(255,255,255,0.08)",
                        "borderRadius": "10px", "padding": "12px 16px",
                        "fontSize": "12px", "color": "rgba(255,255,255,0.45)",
                        "marginTop": "12px", "lineHeight": "1.6",
                    },
                    children="Outil de réflexion assistée uniquement — pas un diagnostic clinique ni un suivi thérapeutique.",
                ),
            ]),

            # Step indicator
            html.Div(
                id="psy-step-indicator",
                className="psy-step-indicator",
                children=[
                    item
                    for i, label in enumerate(steps, 1)
                    for item in ([_step_indicator(i, label, 1)] +
                                 ([_step_separator()] if i < len(steps) else []))
                ],
            ),

            # Step content card
            html.Div(id="psy-step-content", className="psy-card",
                     children=_step1_layout("2024-01-01", now)),

            # Navigation
            html.Div(
                style={"display": "flex", "justifyContent": "space-between",
                       "marginTop": "24px", "gap": "12px"},
                children=[
                    html.Button("← Précédent", id="psy-prev-btn", n_clicks=0,
                                className="psy-nav-btn psy-btn-prev",
                                style={"display": "none"}),
                    html.Button("Suivant →", id="psy-next-btn", n_clicks=0,
                                className="psy-nav-btn psy-btn-next"),
                ],
            ),

            dcc.Store(id="psy-step", data=1),
            dcc.Store(id="psy-selected-sources", data=["verbe", "inconscient", "emotionnel"]),
            dcc.Store(id="psy-store-start", data="2024-01-01"),
            dcc.Store(id="psy-store-end", data=now),
            dcc.Store(id="psy-store-anon", data=["anon"]),
            dcc.Store(id="psy-config", data={}),
        ],
    )


# ─── CALLBACKS ───────────────────────────────────────────────────────────────

@callback(
    Output("psy-step", "data"),
    Output("psy-prev-btn", "style"),
    Output("psy-next-btn", "style"),
    Input("psy-next-btn", "n_clicks"),
    Input("psy-prev-btn", "n_clicks"),
    State("psy-step", "data"),
    prevent_initial_call=True,
)
def navigate_steps(next_clicks, prev_clicks, current_step):
    from dash import ctx
    triggered = ctx.triggered_id
    step = current_step or 1

    if triggered == "psy-next-btn" and step < 4:
        step += 1
    elif triggered == "psy-prev-btn" and step > 1:
        step -= 1

    prev_style = {"display": "block" if step > 1 else "none"}
    next_style = {"display": "none" if step == 4 else "block"}
    
    return step, prev_style, next_style


@callback(
    Output("psy-step-content", "children"),
    Output("psy-step-indicator", "children"),
    Input("psy-step", "data"),
    Input("psy-selected-sources", "data"),
    State("psy-store-start", "data"),
    State("psy-store-end", "data"),
    State("psy-store-anon", "data"),
)
def render_step(step, selected_sources, start, end, anon):
    step = step or 1
    selected_sources = selected_sources or ["verbe", "inconscient", "emotionnel"]
    step_labels = ["Période", "Sources", "Confidentialité", "Génération"]

    indicator = [
        item
        for i, label in enumerate(step_labels, 1)
        for item in ([_step_indicator(i, label, step)] +
                     ([_step_separator()] if i < len(step_labels) else []))
    ]

    if step == 1:
        content = _step1_layout(start, end)
    elif step == 2:
        content = _step2_layout(selected_sources)
    elif step == 3:
        content = _step3_layout(anon)
    else:
        content = _step4_layout()
        
    return content, indicator


@callback(
    Output("psy-store-start", "data"),
    Output("psy-store-end", "data"),
    Input("psy-date-start", "date"),
    Input("psy-date-end", "date"),
    prevent_initial_call=True,
)
def sync_dates(start, end):
    return start, end

@callback(Output("psy-store-anon", "data"), Input("psy-anon-names", "value"), prevent_initial_call=True)
def sync_anon(v): return v


@callback(
    Output("psy-selected-sources", "data"),
    Input({"type": "psy-src-card", "index": ALL}, "n_clicks"),
    State("psy-selected-sources", "data"),
    prevent_initial_call=True
)
def toggle_source(n_clicks_list, current_sources):
    from dash import ctx
    if not ctx.triggered_id:
        return current_sources
    
    source_id = ctx.triggered_id["index"]
    new_sources = list(current_sources) if current_sources else []
    
    if source_id in new_sources:
        if len(new_sources) > 1:  # Keep at least one
            new_sources.remove(source_id)
    else:
        new_sources.append(source_id)
        
    return new_sources


@callback(
    Output("psy-volume-preview", "children"),
    Input("psy-date-start", "date"),
    Input("psy-date-end", "date"),
)
def update_volume_preview(start, end):
    if not start or not end:
        return []

    chips = []
    for src in SOURCES_OPTIONS:
        table_map = {
            "verbe": "tiktok_messages_text",
            "inconscient": "google_searches",
            "emotionnel": "spotify_streams",
            }
        table = table_map[src["id"]]
        path = os.path.join(DELTA_BASE, table)
        vol = 0
        if os.path.exists(path):
            files = [f for f in os.listdir(path) if f.endswith(".parquet")]
            if files:
                try:
                    date_cols = {"tiktok_messages_text": "timestamp_ms",
                                 "google_searches": "event_date",
                                 "spotify_streams": "listen_ts"}
                    df = pd.concat([pd.read_parquet(os.path.join(path, f)) for f in files])
                    dcol = date_cols.get(table)
                    if dcol and dcol in df.columns:
                        df[dcol] = pd.to_datetime(df[dcol], errors="coerce", unit="ms"
                                                   if table == "tiktok_messages_text" else None)
                        df = df[(df[dcol] >= pd.Timestamp(start)) & (df[dcol] <= pd.Timestamp(end))]
                    vol = len(df)
                except Exception:
                    pass

        chips.append(html.Div(
            className=f"psy-chip {'has-data' if vol > 0 else ''}",
            children=[
                html.Span(src["icon"], style={"fontSize": "14px"}),
                html.Span(f"{vol:,}", style={
                    "fontSize": "13px", "fontWeight": "700",
                    "color": "#7c5af6" if vol > 0 else "rgba(255,255,255,0.3)",
                }),
                html.Span(src["label"], style={
                    "fontSize": "12px",
                    "color": "#fff" if vol > 0 else "rgba(255,255,255,0.3)",
                }),
            ],
        ))
    return chips


@callback(
    Output("psy-download", "data"),
    Output("psy-generate-result", "children"),
    Input("psy-generate-btn", "n_clicks"),
    State("psy-store-start", "data"),
    State("psy-store-end", "data"),
    State("psy-selected-sources", "data"),
    State("psy-store-anon", "data"),
    prevent_initial_call=True,
)
def generate_package(n_clicks, start, end, sources, anon_names_val):
    if not n_clicks:
        return no_update, no_update

    start = start or "2024-01-01"
    end = end or datetime.now().strftime("%Y-%m-%d")
    sources = sources or ["verbe", "inconscient", "emotionnel"]
    anon = bool(anon_names_val and "anon" in anon_names_val)

    # Import the builder script from app/psy_utils.py
    try:
        from app.psy_utils import build_package
    except Exception as e:
        error_msg = html.Div(
            f"Erreur d'import utilitaire : {e}",
            style={"color": "#ff453a", "marginBottom": "16px", "fontSize": "14px"},
        )
        return no_update, error_msg

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "Dossier_Psy_Arnaud.zip")
        try:
            build_package(start, end, sources, anon, out_path)
            with open(out_path, "rb") as f:
                zip_data = f.read()
        except Exception as e:
            error_msg = html.Div(
                f"Erreur lors de la génération : {e}",
                style={"color": "#ff453a", "marginBottom": "16px", "fontSize": "14px"},
            )
            return no_update, error_msg

    filename = f"Analyse_Comportementale_{start[:10]}_{end[:10]}.zip"

    success_card = html.Div(
        style={
            "background": "rgba(124,90,246,0.1)",
            "border": "1px solid rgba(124, 90, 246, 0.4)",
            "borderRadius": "14px", "padding": "20px 24px",
            "marginBottom": "20px",
        },
        children=[
            html.Div("✓ DOSSIER PRÊT", style={
                "fontSize": "11px", "fontWeight": "700", "letterSpacing": "2px",
                "color": "#7c5af6", "marginBottom": "8px",
            }),
            html.P("Ton dossier comportemental a été généré et le téléchargement a commencé.", style={
                "color": "#fff", "fontWeight": "600", "marginBottom": "12px",
            }),
            html.P("Si le téléchargement ne se lance pas automatiquement, vérifie tes réglages de navigateur.",
                   style={"color": "rgba(255,255,255,0.5)", "fontSize": "12px", "marginBottom": "16px"}),
            html.Ol(style={"color": "rgba(255,255,255,0.7)", "fontSize": "14px",
                           "lineHeight": "1.8", "paddingLeft": "20px"}, children=[
                html.Li("Ouvre ton LLM (Gemini 2.5 Pro, GPT-4o, Claude…)"),
                html.Li("Glisse-dépose le fichier ZIP dans le chat"),
                html.Li([
                    "Copie l'amorce : ",
                    html.Code(
                        "Voici mon profil comportemental numérique. Analyse les données et commence par une observation sur mes patterns ou évolutions.",
                        style={"fontSize": "12px", "color": "#7c5af6",
                               "background": "rgba(124,90,246,0.1)",
                               "padding": "2px 6px", "borderRadius": "4px"},
                    ),
                ]),
            ]),
        ],
    )

    download = dcc.send_bytes(zip_data, filename=filename)
    return download, success_card
