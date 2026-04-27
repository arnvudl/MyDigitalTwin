"""
Shape of Me — page topology (remplace l'ancienne page Profils comportementaux).
Charge topology_data.json produit par src/scripts/02_topology/02_graph.ipynb
et génère un graphe 3D interactif via 3d-force-graph.
"""
import json
import os
import time
from functools import lru_cache

from dash import html

# ─── PATHS ────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

if os.path.exists("/app/data/warehouse"):
    _DATA_BASE = "/app/data/warehouse"
    ASSETS_DIR = "/app/app/assets"    # ./app est monté en /app/app dans le container dashboard
else:
    _DATA_BASE = os.path.join(_HERE, "..", "..", "data", "warehouse")
    ASSETS_DIR = os.path.join(_HERE, "..", "assets")

TOPOLOGY_JSON_PATH = os.path.join(ASSETS_DIR, "topology_data.json")
TOPOLOGY_HTML_OUT  = os.path.join(ASSETS_DIR, "topology_3d.html")
TOPOLOGY_TEMPLATE  = os.path.join(ASSETS_DIR, "topology_3d_template.html")


# ─── DATA ─────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_topology() -> dict | None:
    """Charge topology_data.json depuis les assets. None si absent."""
    if not os.path.isfile(TOPOLOGY_JSON_PATH):
        return None
    try:
        with open(TOPOLOGY_JSON_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _topology_stats(data: dict) -> tuple[int, int]:
    """Retourne (n_items, n_clusters) depuis le meta du premier lens disponible.

    Structure JSON compound :
      {lens_name: {nodes, links, meta: {n_items, n_clusters, n_item_nodes, ...}}, ...}
    """
    for lens in ("density", "time", "platform"):
        meta = data.get(lens, {}).get("meta", {})
        if meta:
            n_items    = int(meta.get("n_items", 0))
            n_clusters = int(meta.get("n_clusters", 0))
            if n_items or n_clusters:
                return n_items, n_clusters
    return 0, 0


# ─── 3D HTML GENERATOR ────────────────────────────────────────────────────────
def _build_topology_html(data: dict) -> str:
    """Remplace __TOPOLOGY_DATA__ dans le template par le JSON sérialisé."""
    with open(TOPOLOGY_TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    data_json = json.dumps(data, ensure_ascii=False)
    return template.replace("__TOPOLOGY_DATA__", data_json)


# ─── EMPTY STATE ──────────────────────────────────────────────────────────────
def _empty_layout() -> html.Div:
    return html.Div(className="page-wrapper", children=[
        html.Div(
            style={
                "display": "flex", "flexDirection": "column",
                "alignItems": "center", "justifyContent": "center",
                "minHeight": "60vh", "gap": "20px", "textAlign": "center",
                "padding": "60px 32px",
            },
            children=[
                html.Div("🧭", style={"fontSize": "64px"}),
                html.H2(
                    html.Span(["Shape of ", html.Em("Me")]),
                    style={
                        "fontSize": "36px", "fontWeight": "700",
                        "color": "var(--text-primary)", "margin": "0",
                    },
                ),
                html.P(
                    "Le graphe topologique n'est pas encore généré.",
                    style={"fontSize": "16px", "color": "var(--text-secondary)", "margin": "0"},
                ),
                html.P(
                    [
                        "Lance ",
                        html.Code(
                            "src/scripts/02_topology/02_graph.ipynb",
                            style={
                                "background": "rgba(255,255,255,0.08)",
                                "padding": "2px 8px", "borderRadius": "6px",
                                "fontSize": "13px", "fontFamily": "monospace",
                            },
                        ),
                        " pour produire ",
                        html.Code(
                            "topology_data.json",
                            style={
                                "background": "rgba(255,255,255,0.08)",
                                "padding": "2px 8px", "borderRadius": "6px",
                                "fontSize": "13px", "fontFamily": "monospace",
                            },
                        ),
                        ".",
                    ],
                    style={"fontSize": "13px", "color": "var(--text-muted)", "margin": "0"},
                ),
            ],
        )
    ])


# ─── LAYOUT ───────────────────────────────────────────────────────────────────
def layout() -> html.Div:
    data = _load_topology()

    if data is None:
        return _empty_layout()

    # Write the 3D HTML file (always fresh so data is never stale)
    try:
        with open(TOPOLOGY_HTML_OUT, "w", encoding="utf-8") as fh:
            fh.write(_build_topology_html(data))
    except Exception:
        return _empty_layout()

    n_items, n_clusters = _topology_stats(data)
    # generated_at : not in JSON → fall back to file mtime
    try:
        import datetime as _dt
        _mtime = os.path.getmtime(TOPOLOGY_JSON_PATH)
        generated_at = _dt.datetime.fromtimestamp(_mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        generated_at = ""

    # Platforms present across all lenses (cluster nodes only)
    all_platforms: set[str] = set()
    for lens in ("time", "platform", "density"):
        for n in data.get(lens, {}).get("nodes", []):
            if n.get("type", "cluster") == "cluster":
                p = n.get("platform", "")
                if p:
                    all_platforms.add(p)

    platform_labels = sorted(all_platforms)

    return html.Div(className="page-wrapper", children=[
        html.Div(
            style={"maxWidth": "1100px", "margin": "0 auto", "padding": "40px 32px 80px"},
            children=[

                # ── Hero ──────────────────────────────────────────────────────
                html.Div(
                    className="home-hero",
                    style={"textAlign": "center"},
                    children=[
                        html.P("Topologie des intérêts · TDA Mapper", className="home-hero-label"),
                        html.H1(
                            html.Span(["Shape of ", html.Em("Me")]),
                            className="home-hero-title",
                            style={"fontSize": "56px"},
                        ),
                        html.P(
                            f"{n_items:,} items · {n_clusters} clusters"
                            + ((" · " + ", ".join(p.capitalize() for p in platform_labels)) if platform_labels else ""),
                            className="home-hero-sub",
                        ),
                    ],
                ),

                # ── Graph iframe ──────────────────────────────────────────────
                html.Iframe(
                    src=f"/assets/topology_3d.html?v={int(time.time())}",
                    style={
                        "width": "100%",
                        "height": "720px",
                        "border": "none",
                        "borderRadius": "20px",
                        "overflow": "hidden",
                        "display": "block",
                        "marginBottom": "32px",
                        "boxShadow": "0 10px 40px rgba(0,0,0,0.5)",
                    },
                ),

                # ── Caption ───────────────────────────────────────────────────
                html.Div(
                    style={"display": "flex", "justifyContent": "space-between",
                           "alignItems": "center", "marginBottom": "40px"},
                    children=[
                        html.P(
                            [
                                "Chaque ",
                                html.Strong("nœud", style={"color": "var(--text-primary)"}),
                                " = un cluster d'items similaires. "
                                "Les ",
                                html.Strong("arêtes", style={"color": "var(--text-primary)"}),
                                " connectent les clusters qui partagent des éléments. "
                                "3 lentilles : temporelle, par plateforme, par densité sémantique.",
                            ],
                            style={
                                "fontSize": "13px", "color": "var(--text-muted)",
                                "lineHeight": "1.6", "maxWidth": "580px",
                            },
                        ),
                        *([html.P(
                            f"Généré le {generated_at[:10]}",
                            style={"fontSize": "11px", "color": "var(--text-muted)",
                                   "whiteSpace": "nowrap"},
                        )] if generated_at else []),
                    ],
                ),

                # ── Platform legend chips ─────────────────────────────────────
                html.Div(
                    style={"display": "flex", "flexWrap": "wrap", "gap": "10px",
                           "marginBottom": "12px"},
                    children=[
                        html.Div(
                            style={
                                "display": "flex", "alignItems": "center",
                                "gap": "7px",
                                "background": "rgba(255,255,255,0.04)",
                                "border": "1px solid rgba(255,255,255,0.08)",
                                "borderRadius": "20px", "padding": "5px 14px",
                            },
                            children=[
                                html.Div(style={
                                    "width": "8px", "height": "8px", "borderRadius": "50%",
                                    "background": _PLATFORM_COLORS.get(p, "#8b8fa8"),
                                    "flexShrink": "0",
                                }),
                                html.Span(
                                    p.capitalize(),
                                    style={"fontSize": "12px",
                                           "color": "rgba(255,255,255,0.55)"},
                                ),
                            ],
                        )
                        for p in platform_labels
                    ],
                ),

            ],
        ),
    ])


# ─── Platform colour map (mirrors topology_3d_template.html) ─────────────────
_PLATFORM_COLORS: dict[str, str] = {
    "spotify":   "#1DB954",
    "twitter":   "#1DA1F2",
    "tiktok":    "#69C9D0",
    "instagram": "#E1306C",
    "youtube":   "#FF4040",
    "netflix":   "#E50914",
}
