import os
from functools import lru_cache
from urllib.parse import quote

import pandas as pd
import plotly.express as px
from dash import Input, Output, callback, dcc, html
from app.icons import svg_icon, IMAGE
from config import DATA_ROOT, PHOTO_CLUSTERS_DIR, SPARK_DATA_ROOT

# ─── CONFIG ──────────────────────────────────────────────────────────────────
CLUSTERS_DIR = PHOTO_CLUSTERS_DIR
_SPARK_PREFIX = SPARK_DATA_ROOT

CLUSTER_COLORS = ["#c13584", "#833ab4", "#fd1d1d", "#fcaf45", "#4fc3f7"]

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def _spark_to_local(spark_path: str) -> str:
    if spark_path and spark_path.startswith(_SPARK_PREFIX):
        return os.path.normpath(DATA_ROOT + spark_path[len(_SPARK_PREFIX):])
    return os.path.normpath(spark_path) if spark_path else spark_path


@lru_cache(maxsize=1)
def _read_clusters() -> pd.DataFrame:
    if not os.path.exists(CLUSTERS_DIR):
        return pd.DataFrame()
    files = [
        os.path.join(CLUSTERS_DIR, f)
        for f in os.listdir(CLUSTERS_DIR)
        if f.endswith(".parquet") and not f.startswith(".")
    ]
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["local_path"] = df["path"].apply(_spark_to_local)
    # Compatibilité V1 (pca_x/pca_y) → V2 (umap_x/umap_y)
    if "pca_x" in df.columns and "umap_x" not in df.columns:
        df = df.rename(columns={"pca_x": "umap_x", "pca_y": "umap_y"})
    return df


def _photo_url(local_path: str) -> str:
    norm_path = os.path.normpath(local_path)
    norm_root = os.path.normpath(DATA_ROOT)
    if norm_path.startswith(norm_root):
        rel = norm_path[len(norm_root):].lstrip('/\\')
    else:
        rel = norm_path.lstrip('/\\')
    rel = rel.replace('\\', '/')
    _safe = "/:@!$&'()*+,;="
    return f'/photo/{quote(rel, safe=_safe)}'


def _scatter_fig(df: pd.DataFrame, selected_cluster=None):
    df = df.copy()
    df["opacity"] = df["cluster"].apply(
        lambda c: 1.0 if selected_cluster is None or int(c) == int(selected_cluster) else 0.15
    )
    fig = px.scatter(
        df, x="umap_x", y="umap_y",
        color="cluster_label",
        color_discrete_sequence=CLUSTER_COLORS,
        hover_data={"filename": True, "cluster_label": True, "umap_x": False, "umap_y": False},
        labels={"cluster_label": "Cluster", "umap_x": "", "umap_y": ""},
    )
    fig.update_traces(marker=dict(size=5, opacity=0.75))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e5e7",
        legend_title_text="",
        margin=dict(l=0, r=0, t=8, b=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig


def _photo_grid(rows: pd.DataFrame) -> html.Div:
    imgs = []
    for _, row in rows.iterrows():
        local = os.path.normpath(row["local_path"])
        if os.path.exists(local):
            imgs.append(
                html.Img(
                    src=_photo_url(local),
                    title=row["filename"],
                    className="photo-item",
                    style={
                        "width": "100%", "aspectRatio": "1/1",
                        "objectFit": "cover", "borderRadius": "6px",
                        "display": "block", "cursor": "pointer",
                    },
                )
            )
    if not imgs:
        return html.Div("Aucune photo disponible.", style={"color": "#555", "fontSize": "14px"})
    return html.Div(
        imgs,
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fill, minmax(120px, 1fr))",
            "gap": "6px",
        },
    )


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    df = _read_clusters()

    if df.empty:
        return html.Div(className="page-wrapper", children=[
            html.Div(className="page-empty-state", children=[
                html.Div(svg_icon(IMAGE, size="56"), style={"color": "var(--text-secondary)"}),
                html.H2("Clustering Photos",
                        style={"fontSize": "28px", "fontWeight": "700",
                               "color": "var(--text-primary)"}),
                html.P("Lance d'abord 05_CLIP/02_clip_clustering.ipynb.",
                       style={"fontSize": "14px", "color": "var(--text-secondary)"}),
            ])
        ])

    cluster_ids = sorted(df["cluster"].unique())
    n_photos = len(df)

    # Chips de sélection cluster
    chips = [
        html.Span(
            "Tous",
            id={"type": "photo-cluster-chip", "index": -999},
            className="filter-chip filter-chip-active",
            n_clicks=0,
        )
    ]
    for i, cid in enumerate(cluster_ids):
        label = df[df["cluster"] == cid]["cluster_label"].iloc[0]
        count = len(df[df["cluster"] == cid])
        chips.append(
            html.Span(
                f"{label} ({count})",
                id={"type": "photo-cluster-chip", "index": int(cid)},
                className="filter-chip",
                n_clicks=0,
            )
        )

    return html.Div(className="page-wrapper", children=[
        html.Div(style={"maxWidth": "1200px", "margin": "0 auto", "padding": "40px 24px",
                        "display": "flex", "flexDirection": "column", "gap": "36px"}, children=[

            # Hero
            html.Div(className="home-hero", children=[
                html.P(f"{n_photos} photos • {len(cluster_ids)} clusters", className="home-hero-label"),
                html.H1(
                    html.Span(["Photos ", html.Em("Instagram")]),
                    className="home-hero-title",
                    style={"fontSize": "56px"},
                ),
                html.P("Clustering visuel par similarité CLIP (ViT-L/14).", className="home-hero-sub"),
            ]),

            # Scatter PCA
            html.Div(children=[
                html.P("Carte visuelle UMAP 2D", className="section-label"),
                dcc.Graph(
                    id="photo-scatter",
                    figure=_scatter_fig(df),
                    config={"displayModeBar": False},
                    style={"height": "380px", "borderRadius": "12px", "overflow": "hidden",
                           "background": "rgba(28,28,30,0.6)"},
                ),
            ]),

            # Chips
            html.Div(className="filter-bar", children=[
                html.Div("Cluster", className="filter-label"),
                html.Div(className="filter-chips-row", children=chips),
            ]),

            # Store cluster sélectionné
            dcc.Store(id="photo-selected-cluster", data=-999),

            # Header du cluster actif
            html.Div(id="photo-cluster-header"),

            # Grille de photos (toutes)
            html.Div(id="photo-grid-container"),
        ]),

        # ─── Lightbox overlay ─────────────────────────────────────────────────
        html.Div(
            id="lightbox-overlay",
            style={
                "display": "none",
                "position": "fixed", "inset": "0", "zIndex": "9999",
                "background": "rgba(0,0,0,0.93)",
                "alignItems": "center", "justifyContent": "center",
            },
            children=[
                # Close button
                html.Button(
                    "×",
                    id="lightbox-close",
                    style={
                        "position": "absolute", "top": "16px", "right": "20px",
                        "background": "none", "border": "none", "color": "#fff",
                        "fontSize": "36px", "cursor": "pointer", "lineHeight": "1",
                        "opacity": "0.8",
                    },
                ),
                # Prev
                html.Button(
                    "‹",
                    id="lightbox-prev",
                    style={
                        "position": "absolute", "left": "16px",
                        "background": "rgba(255,255,255,0.1)", "border": "none",
                        "color": "#fff", "fontSize": "40px", "cursor": "pointer",
                        "borderRadius": "50%", "width": "52px", "height": "52px",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "lineHeight": "1",
                    },
                ),
                # Image
                html.Img(
                    id="lightbox-img",
                    src="",
                    style={
                        "maxWidth": "90vw", "maxHeight": "85vh",
                        "objectFit": "contain", "borderRadius": "4px",
                        "boxShadow": "0 8px 48px rgba(0,0,0,0.6)",
                    },
                ),
                # Next
                html.Button(
                    "›",
                    id="lightbox-next",
                    style={
                        "position": "absolute", "right": "16px",
                        "background": "rgba(255,255,255,0.1)", "border": "none",
                        "color": "#fff", "fontSize": "40px", "cursor": "pointer",
                        "borderRadius": "50%", "width": "52px", "height": "52px",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "lineHeight": "1",
                    },
                ),
                # Counter
                html.Div(
                    id="lightbox-counter",
                    style={
                        "position": "absolute", "bottom": "20px",
                        "color": "rgba(255,255,255,0.55)", "fontSize": "13px",
                        "letterSpacing": "1px",
                    },
                ),
            ],
        ),
    ])


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
from dash import ALL, ctx

@callback(
    Output("photo-selected-cluster", "data"),
    Input({"type": "photo-cluster-chip", "index": ALL}, "n_clicks"),
    Input({"type": "photo-cluster-chip", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def select_cluster(n_clicks_list, chip_ids):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
        return -999
    return ctx.triggered_id.get("index", -999)


@callback(
    Output({"type": "photo-cluster-chip", "index": ALL}, "className"),
    Input("photo-selected-cluster", "data"),
    Input({"type": "photo-cluster-chip", "index": ALL}, "id"),
)
def update_chip_styles(selected, chip_ids):
    return [
        "filter-chip filter-chip-active" if int(chip["index"]) == int(selected) else "filter-chip"
        for chip in chip_ids
    ]


@callback(
    Output("photo-scatter", "figure"),
    Output("photo-cluster-header", "children"),
    Output("photo-grid-container", "children"),
    Input("photo-selected-cluster", "data"),
)
def update_view(selected_cluster):
    df = _read_clusters()
    if df.empty:
        return {}, html.Div(), html.Div()

    # Scatter
    sel = None if selected_cluster == -999 else selected_cluster
    fig = _scatter_fig(df, sel)

    # Sous-ensemble
    if selected_cluster == -999:
        sub = df
        header = html.Div(
            f"{len(df)} photos — tous les clusters",
            style={"fontSize": "14px", "color": "#888"},
        )
    else:
        sub = df[df["cluster"].astype(int) == int(selected_cluster)]
        label = sub["cluster_label"].iloc[0] if not sub.empty else ""
        color = CLUSTER_COLORS[int(selected_cluster) % len(CLUSTER_COLORS)]
        header = html.Div(style={"display": "flex", "alignItems": "center", "gap": "12px"}, children=[
            html.Div(style={"width": "4px", "height": "24px", "borderRadius": "2px", "background": color}),
            html.Div(label, style={"fontSize": "20px", "fontWeight": "600", "color": "#e5e5e7"}),
            html.Div(f"{len(sub)} photos", style={
                "fontSize": "13px", "color": "#888",
                "background": "rgba(255,255,255,0.06)",
                "padding": "3px 10px", "borderRadius": "20px",
            }),
        ])

    grid = _photo_grid(sub)
    return fig, header, grid
