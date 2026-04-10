import os

import dash_cytoscape as cyto
import pandas as pd
from dash import Input, Output, callback, html, dash_table, dcc

# ─── CHEMINS ─────────────────────────────────────────────────────────────────
if os.path.exists("/app/warehouse"):
    WAREHOUSE = "/app/warehouse"
else:
    WAREHOUSE = "warehouse"

PARQUET = os.path.join(WAREHOUSE, "social_graph.parquet")

# ─── DONNÉES ─────────────────────────────────────────────────────────────────
def _load():
    if not os.path.exists(PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(PARQUET)


def _build_elements(df: pd.DataFrame) -> list:
    if df.empty:
        return []

    w_max = df["weight"].max()
    elements = []

    elements.append({
        "data": {"id": "arnaud", "label": "Arnaud", "role": "center"},
        "classes": "center-node",
    })

    for _, row in df.iterrows():
        node_id    = row["node_id"]
        label      = row["label"]
        weight     = row["weight"]
        is_close   = bool(row["in_close_friends"])
        msg_count  = int(row["message_count"])
        # Taille : 20–60 px (plus compact, moins de chevauchement)
        size       = 20 + int(40 * (weight / w_max))
        edge_width = 1 + int(6 * (weight / w_max))

        elements.append({
            "data": {
                "id": node_id,
                "label": label,
                "weight": weight,
                "msg_count": msg_count,
                "is_close": is_close,
                "size": size,
                "edge_width": edge_width,
            },
            "classes": "close-node" if is_close else "follower-node",
        })
        elements.append({
            "data": {
                "source": "arnaud",
                "target": node_id,
                "weight": edge_width,
                "node_id": node_id,
            },
            "classes": "close-edge" if is_close else "follower-edge",
        })

    return elements


# ─── STYLESHEET DE BASE ───────────────────────────────────────────────────────
def _base_stylesheet(hovered_id: str | None = None) -> list:
    """
    hovered_id=None        → état repos (liens quasi invisibles, labels discrets)
    hovered_id="arnaud"    → tout est mis en valeur
    hovered_id="xxx_id"    → seulement le lien vers cette personne est mis en valeur
    """
    all_dim  = hovered_id is not None and hovered_id != "arnaud"

    # Opacité des nœuds non-focalisés
    node_opacity      = 0.25 if all_dim else 1.0
    label_opacity     = 0.0  if all_dim else 0.75   # labels masqués par défaut sauf hover
    edge_opacity_def  = 0.0  if all_dim else 0.07   # liens quasi-invisibles au repos
    edge_opacity_cf   = 0.0  if all_dim else 0.15

    sheet = [
        # ── Nœud central ─────────────────────────────────────────────────────
        {
            "selector": ".center-node",
            "style": {
                "width": 70, "height": 70,
                "background-color": "#ffffff",
                "label": "data(label)",
                "color": "#000000",
                "font-size": 13, "font-weight": "bold",
                "text-valign": "center", "text-halign": "center",
                "border-width": 0,
                "opacity": 1,
            },
        },
        # ── Close friends ─────────────────────────────────────────────────────
        {
            "selector": ".close-node",
            "style": {
                "width": "data(size)", "height": "data(size)",
                "background-color": "#bf5af2",
                "label": "data(label)",
                "color": "#ffffff",
                "font-size": 11, "font-weight": "700",
                "text-valign": "bottom", "text-margin-y": 5,
                "text-opacity": label_opacity,
                "border-width": 2, "border-color": "#d97df7",
                "opacity": node_opacity,
                "text-background-color": "#000000",
                "text-background-opacity": 0.5 if label_opacity > 0 else 0,
                "text-background-padding": "3px",
                "text-background-shape": "roundrectangle",
            },
        },
        # ── Followers ─────────────────────────────────────────────────────────
        {
            "selector": ".follower-node",
            "style": {
                "width": "data(size)", "height": "data(size)",
                "background-color": "#48484a",
                "label": "data(label)",
                "color": "#ffffff",
                "font-size": 11, "font-weight": "600",
                "text-valign": "bottom", "text-margin-y": 5,
                "text-opacity": label_opacity,
                "border-width": 1, "border-color": "rgba(255,255,255,0.2)",
                "opacity": node_opacity,
                "text-background-color": "#000000",
                "text-background-opacity": 0.5 if label_opacity > 0 else 0,
                "text-background-padding": "3px",
                "text-background-shape": "roundrectangle",
            },
        },
        # ── Arêtes close friends ──────────────────────────────────────────────
        {
            "selector": ".close-edge",
            "style": {
                "width": "data(weight)",
                "line-color": f"rgba(191,90,242,{edge_opacity_cf})",
                "curve-style": "straight",
                "opacity": 1,
            },
        },
        # ── Arêtes followers ──────────────────────────────────────────────────
        {
            "selector": ".follower-edge",
            "style": {
                "width": "data(weight)",
                "line-color": f"rgba(180,180,200,{edge_opacity_def})",
                "curve-style": "straight",
                "opacity": 1,
            },
        },
    ]

    # ── Nœud survolé : pleine visibilité ─────────────────────────────────────
    if hovered_id and hovered_id != "arnaud":
        sheet += [
            {
                "selector": f'node[id = "{hovered_id}"]',
                "style": {
                    "opacity": 1,
                    "text-opacity": 1,
                    "text-background-opacity": 0.6,
                    "border-width": 3,
                    "border-color": "#ffffff",
                },
            },
            # Arête vers ce nœud — couleur vive selon type
            {
                "selector": f'edge[target = "{hovered_id}"].close-edge',
                "style": {
                    "line-color": "rgba(191,90,242,0.9)",
                    "width": 3,
                },
            },
            {
                "selector": f'edge[target = "{hovered_id}"].follower-edge',
                "style": {
                    "line-color": "rgba(100,180,255,0.85)",
                    "width": 2,
                },
            },
        ]

    # ── Survol Arnaud : tout illuminé ────────────────────────────────────────
    if hovered_id == "arnaud":
        sheet += [
            {
                "selector": ".close-node, .follower-node",
                "style": {"opacity": 1, "text-opacity": 1, "text-background-opacity": 0.5},
            },
            {
                "selector": ".close-edge",
                "style": {"line-color": "rgba(191,90,242,0.6)"},
            },
            {
                "selector": ".follower-edge",
                "style": {"line-color": "rgba(100,180,255,0.35)"},
            },
        ]

    return sheet


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    df      = _load()
    elements = _build_elements(df)
    n_close  = int(df["in_close_friends"].sum()) if not df.empty else 0
    n_total  = len(df)
    n_msgs   = int(df["message_count"].sum()) if not df.empty else 0

    # Préparation données tableau
    table_data = df[["label", "message_count"]].rename(columns={"label": "Pseudo", "message_count": "Messages"}).to_dict("records")

    return html.Div(
        style={"paddingTop": "64px", "minHeight": "100vh", "background": "var(--bg-base)"},
        children=[
            # ── Header ───────────────────────────────────────────────────────
            html.Div(
                style={"padding": "40px 48px 24px"},
                children=[
                    html.P("GRAPHE SOCIAL", style={
                        "fontFamily": "var(--font-display, monospace)",
                        "fontSize": "11px", "fontWeight": "600",
                        "letterSpacing": "3px", "textTransform": "uppercase",
                        "color": "var(--text-muted)", "marginBottom": "12px",
                    }),
                    html.H1("Ton réseau", style={
                        "fontSize": "40px", "fontWeight": "800",
                        "color": "var(--text-primary)", "margin": "0 0 8px",
                    }),
                    html.P(
                        f"{n_total} conversations • {n_close} close friends • {n_msgs:,} messages",
                        style={"fontSize": "15px", "color": "var(--text-secondary)", "margin": 0},
                    ),
                ],
            ),

            # ── Graphe + info panel ──────────────────────────────────────────
            html.Div(
                style={"display": "flex", "gap": "24px", "padding": "0 48px 20px"},
                children=[
                    html.Div(
                        style={
                            "flex": "1",
                            "background": "rgba(18,18,20,0.85)",
                            "borderRadius": "16px",
                            "border": "1px solid rgba(255,255,255,0.08)",
                            "overflow": "hidden",
                            "height": "600px",
                        },
                        children=[
                            cyto.Cytoscape(
                                id="social-graph",
                                elements=elements,
                                layout={
                                    "name": "cose",
                                    "idealEdgeLength": 220,
                                    "nodeOverlap": 4,
                                    "refresh": 20,
                                    "fit": True,
                                    "padding": 60,
                                    "randomize": False,
                                    "componentSpacing": 120,
                                    "nodeRepulsion": 2000000,
                                    "edgeElasticity": 80,
                                    "nestingFactor": 5,
                                    "gravity": 40,
                                    "numIter": 1500,
                                    "initialTemp": 300,
                                    "coolingFactor": 0.95,
                                    "minTemp": 1.0,
                                },
                                style={"width": "100%", "height": "600px", "background": "transparent"},
                                stylesheet=_base_stylesheet(),
                                responsive=True,
                            )
                        ],
                    ),
                    html.Div(
                        id="social-info-panel",
                        style={
                            "width": "260px", "flexShrink": 0,
                            "background": "rgba(28,28,30,0.7)",
                            "borderRadius": "16px",
                            "border": "1px solid rgba(255,255,255,0.1)",
                            "padding": "24px",
                            "height": "fit-content",
                            "alignSelf": "flex-start",
                        },
                        children=_empty_panel(),
                    ),
                ],
            ),

            # ── Tableau des interactions ─────────────────────────────────────
            html.Div(
                style={"padding": "0 48px 60px"},
                children=[
                    html.H2("Détail des interactions", style={
                        "fontSize": "20px", "fontWeight": "700",
                        "color": "var(--text-primary)", "marginBottom": "20px",
                    }),
                    dash_table.DataTable(
                        id="social-table",
                        columns=[
                            {"name": "Pseudo", "id": "Pseudo", "type": "text"},
                            {"name": "Messages", "id": "Messages", "type": "numeric"},
                        ],
                        data=table_data,
                        sort_action="native",
                        filter_action="native",
                        page_size=15,
                        style_table={"borderRadius": "12px", "overflow": "hidden", "border": "1px solid rgba(255,255,255,0.08)"},
                        style_header={
                            "backgroundColor": "rgba(30,30,35,1)",
                            "color": "var(--text-primary)",
                            "fontWeight": "bold",
                            "border": "1px solid rgba(255,255,255,0.08)",
                            "padding": "12px",
                        },
                        style_cell={
                            "backgroundColor": "rgba(20,20,25,0.7)",
                            "color": "var(--text-secondary)",
                            "border": "1px solid rgba(255,255,255,0.04)",
                            "padding": "12px",
                            "textAlign": "left",
                            "fontFamily": "inherit",
                        },
                        style_data_conditional=[
                            {
                                "if": {"state": "active"},
                                "backgroundColor": "rgba(109, 94, 245, 0.2)",
                                "border": "1px solid var(--accent-primary)",
                            }
                        ],
                    ),
                ],
            ),
        ],
    )


# ─── HELPERS PANEL ───────────────────────────────────────────────────────────
def _empty_panel():
    return [html.P("Passe la souris sur un nœud", style={
        "fontSize": "13px", "color": "var(--text-muted)",
        "textAlign": "center", "marginTop": "60px",
    })]


def _node_panel(node_data: dict) -> list:
    label    = node_data.get("label", "")
    msg      = node_data.get("msg_count", 0)
    is_close = node_data.get("is_close", False)

    return [
        html.H3(f"@{label}", style={
            "fontSize": "18px", "fontWeight": "700",
            "color": "var(--text-primary)", "margin": "0 0 8px",
            "wordBreak": "break-all",
        }),
        html.Span("⭐ Close friend" if is_close else "Follower", style={
            "display": "inline-block", "padding": "3px 10px",
            "borderRadius": "12px", "fontSize": "12px", "fontWeight": "600",
            "background": "#bf5af2" if is_close else "rgba(255,255,255,0.1)",
            "color": "#fff", "marginBottom": "16px",
        }),
        html.Hr(style={"border": "none", "borderTop": "1px solid rgba(255,255,255,0.1)", "margin": "12px 0"}),
        html.Div(style={"display": "flex", "justifyContent": "space-between"}, children=[
            html.Span("💬 Messages", style={"fontSize": "13px", "color": "var(--text-muted)"}),
            html.Span(f"{msg:,}", style={"fontSize": "14px", "fontWeight": "600", "color": "var(--text-primary)"}),
        ]),
    ]


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
@callback(
    Output("social-graph", "stylesheet"),
    Output("social-info-panel", "children"),
    Input("social-graph", "mouseoverNodeData"),
)
def on_hover(hover_data):
    if not hover_data:
        return _base_stylesheet(None), _empty_panel()

    hovered_id = hover_data.get("id")
    panel = _node_panel(hover_data) if hovered_id != "arnaud" else _empty_panel()
    return _base_stylesheet(hovered_id), panel
