import json
import os

import pandas as pd
from dash import html, dash_table

# ─── PATHS ───────────────────────────────────────────────────────────────────
WAREHOUSE = "/app/warehouse" if os.path.exists("/app/warehouse") else "warehouse"
PARQUET   = os.path.join(WAREHOUSE, "social_graph.parquet")

_HERE      = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(_HERE, "..", "assets")


# ─── DATA ────────────────────────────────────────────────────────────────────
def _load():
    if not os.path.exists(PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(PARQUET)


def _df_to_graph_data(df: pd.DataFrame) -> dict:
    nodes = [{"id": "arnaud", "label": "Arnaud", "is_close": False, "msg_count": 0, "val": 80}]
    links = []

    if df.empty:
        return {"nodes": nodes, "links": links}

    w_max = df["message_count"].max()

    for _, row in df.iterrows():
        node_id   = str(row["node_id"])
        label     = str(row["label"])
        msg_count = int(row["message_count"])
        is_close  = bool(row["in_close_friends"])
        # nodeVal drives sphere VOLUME (radius = cbrt(val) * nodeRelSize).
        # Scaling is non-linear so size differences are clearly visible.
        ratio = msg_count / w_max          # 0.0 → 1.0
        if is_close:
            val = int(20 + 44 * ratio)     # 20 → 64  (radius ≈ 2.7× → 4.0×)
        else:
            val = int(1  + 11 * ratio)     # 1  → 12  (radius ≈ 1.0× → 2.3×)

        nodes.append({
            "id": node_id, "label": label,
            "is_close": is_close, "msg_count": msg_count, "val": val,
        })
        links.append({
            "source": "arnaud", "target": node_id,
            "is_close": is_close,
            "width": 0.8 + int(2 * ratio),
        })

    return {"nodes": nodes, "links": links}


# ─── 3D HTML GENERATOR ───────────────────────────────────────────────────────
def _build_3d_html(df: pd.DataFrame) -> str:
    data_json = json.dumps(_df_to_graph_data(df))

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8"/>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      background: radial-gradient(ellipse at 50% 40%, #130d2e 0%, #07051a 55%, #030210 100%);
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
    }}
    #g {{ width:100vw; height:100vh; }}

    /* ── Info card (bottom-right) ── */
    #card {{
      position: fixed; bottom: 28px; right: 28px; width: 230px;
      background: rgba(10, 7, 26, 0.80);
      backdrop-filter: blur(28px) saturate(160%);
      -webkit-backdrop-filter: blur(28px) saturate(160%);
      border: 1px solid rgba(168,85,247,0.22);
      border-radius: 20px; padding: 20px 22px;
      color:#fff; pointer-events:none;
      box-shadow: 0 12px 48px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(255,255,255,0.04);
      opacity:0; transform:translateY(14px);
      transition: opacity .22s ease, transform .28s cubic-bezier(.34,1.5,.64,1);
    }}
    #card.on {{ opacity:1; transform:translateY(0); }}
    #card-avatar {{
      width:42px; height:42px; border-radius:50%;
      display:flex; align-items:center; justify-content:center;
      font-size:15px; font-weight:700; margin-bottom:13px;
      background:rgba(168,85,247,.18); border:1.5px solid rgba(168,85,247,.5);
      letter-spacing:.5px;
    }}
    #card-avatar.fol {{
      background:rgba(59,79,160,.18); border-color:rgba(99,119,200,.45);
    }}
    #card-name {{ font-size:15px; font-weight:700; color:#ede8ff; margin-bottom:4px; }}
    #card-badge {{
      display:inline-block; font-size:10px; font-weight:700;
      letter-spacing:.8px; text-transform:uppercase;
      padding:3px 10px; border-radius:20px; margin-bottom:15px;
    }}
    #card-badge.cf  {{ background:rgba(168,85,247,.22); color:#c084fc; }}
    #card-badge.fol {{ background:rgba(59,79,160,.22);  color:#93a8d4; }}
    .card-row {{
      display:flex; justify-content:space-between; align-items:center;
      padding-top:12px; border-top:1px solid rgba(255,255,255,.07);
    }}
    .card-row-lbl {{ font-size:12px; color:rgba(255,255,255,.4); }}
    .card-row-val {{ font-size:14px; font-weight:600; color:#e8dfff; }}

    /* ── Legend ── */
    #legend {{
      position:fixed; top:18px; right:18px;
      background:rgba(10,7,26,.72);
      backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
      border:1px solid rgba(255,255,255,.08);
      border-radius:14px; padding:13px 16px;
      color:#fff; font-size:12px; pointer-events:none;
    }}
    .leg {{ display:flex; align-items:center; gap:9px; margin-bottom:7px; }}
    .leg:last-child {{ margin-bottom:0; }}
    .leg-dot {{ width:9px; height:9px; border-radius:50%; flex-shrink:0; }}
    .leg-lbl {{ color:rgba(255,255,255,.55); }}

    /* ── Force-graph tooltip override ── */
    #graph-tooltip {{
      pointer-events: none !important;
      background: transparent !important;
      border: none !important;
      padding: 0 !important;
    }}

    /* ── Hint ── */
    #hint {{
      position:fixed; bottom:20px; left:50%; transform:translateX(-50%);
      background:rgba(10,7,26,.65); backdrop-filter:blur(12px);
      border:1px solid rgba(255,255,255,.07); border-radius:30px;
      padding:7px 18px; font-size:11px; color:rgba(255,255,255,.38);
      pointer-events:none; letter-spacing:.3px;
      transition:opacity 1s ease;
    }}
  </style>
</head>
<body>
  <div id="g"></div>

  <!-- Info card -->
  <div id="card">
    <div id="card-avatar">AB</div>
    <div id="card-name">@username</div>
    <div id="card-badge" class="cf">⭐ Close Friend</div>
    <div class="card-row">
      <span class="card-row-lbl">💬 Messages</span>
      <span class="card-row-val" id="card-msgs">—</span>
    </div>
  </div>

  <!-- Legend -->
  <div id="legend">
    <div class="leg">
      <div class="leg-dot" style="background:#f0f0ff;box-shadow:0 0 5px #fff"></div>
      <span class="leg-lbl">Arnaud</span>
    </div>
    <div class="leg">
      <div class="leg-dot" style="background:#a855f7;box-shadow:0 0 5px rgba(168,85,247,.9)"></div>
      <span class="leg-lbl">Close friends</span>
    </div>
    <div class="leg">
      <div class="leg-dot" style="background:#3b4fa0"></div>
      <span class="leg-lbl">Followers</span>
    </div>
  </div>

  <!-- Hint -->
  <div id="hint">Drag to orbit &nbsp;·&nbsp; Scroll to zoom &nbsp;·&nbsp; Click to focus</div>

  <script src="/assets/3d-force-graph.min.js"></script>
  <script>
    const graphData = {data_json};

    let hoveredId = null;

    function nColor(n) {{
      if (n.id === 'arnaud') return '#f0f0ff';
      if (hoveredId && n.id !== hoveredId) return n.is_close ? '#6a2fa0' : '#232338';
      return n.is_close ? '#a855f7' : '#3b4fa0';
    }}
    function lColor(l) {{
      const tgt = typeof l.target === 'object' ? l.target.id : l.target;
      if (hoveredId && tgt !== hoveredId) return 'rgba(0,0,0,0)';
      return l.is_close ? 'rgba(168,85,247,0.55)' : 'rgba(59,79,160,0.2)';
    }}

    const Graph = ForceGraph3D({{ controlType: 'orbit' }})(document.getElementById('g'))
      .graphData(graphData)
      .backgroundColor('rgba(0,0,0,0)')
      .showNavInfo(false)
      .nodeVal(n => n.val)
      .nodeRelSize(4)
      .nodeColor(nColor)
      .nodeOpacity(0.92)
      .nodeResolution(24)
      .linkColor(lColor)
      .linkWidth(l => l.width)
      .linkDirectionalParticles(l => l.is_close ? 6 : 2)
      .linkDirectionalParticleWidth(l => l.is_close ? 2.5 : 1.2)
      .linkDirectionalParticleColor(l => l.is_close ? '#c084fc' : '#6b7db3')
      .linkDirectionalParticleSpeed(l => l.is_close ? 0.005 : 0.003)
      .nodeLabel(node => {{
        const badge = node.is_close
          ? '<span style="background:rgba(168,85,247,.25);color:#c084fc;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase">⭐ Close Friend</span>'
          : (node.id === 'arnaud' ? '' : '<span style="background:rgba(59,79,160,.2);color:#93a8d4;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase">Follower</span>');
        const msgs = node.msg_count > 0
          ? `<div style="margin-top:6px;font-size:12px;color:rgba(255,255,255,.45)">💬 ${{node.msg_count.toLocaleString()}} messages</div>`
          : '';
        return `<div style="
          background:rgba(10,7,26,.88);
          backdrop-filter:blur(16px);
          border:1px solid rgba(168,85,247,.2);
          border-radius:12px;
          padding:10px 14px;
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          pointer-events:none;
          min-width:120px;
        ">
          <div style="font-size:14px;font-weight:700;color:#ede8ff;margin-bottom:5px">${{node.label}}</div>
          ${{badge}}
          ${{msgs}}
        </div>`;
      }})

      .onNodeHover(node => {{
        hoveredId = node ? node.id : null;
        Graph.nodeColor(nColor).linkColor(lColor);
        document.body.style.cursor = node ? 'pointer' : 'default';

        const card = document.getElementById('card');
        if (!node || node.id === 'arnaud') {{ card.classList.remove('on'); return; }}

        const cf = node.is_close;
        const av = document.getElementById('card-avatar');
        av.textContent = node.label.slice(0,2).toUpperCase();
        av.className   = cf ? 'cf' : 'fol';
        document.getElementById('card-name').textContent = '@' + node.label;
        const badge = document.getElementById('card-badge');
        badge.textContent = cf ? '⭐ Close Friend' : 'Follower';
        badge.className   = 'card-badge ' + (cf ? 'cf' : 'fol');
        document.getElementById('card-msgs').textContent = node.msg_count.toLocaleString();
        card.classList.add('on');
      }})

      .onNodeClick(node => {{
        const len = Math.hypot(node.x||.01, node.y||.01, node.z||.01);
        Graph.cameraPosition(
          {{ x: node.x*(len+150)/len, y: node.y*(len+150)/len, z: node.z*(len+150)/len }},
          node, 900
        );
      }})
      .onBackgroundClick(() => {{
        Graph.cameraPosition({{x:0, y:0, z:500}}, {{x:0,y:0,z:0}}, 800);
      }});

    Graph.d3Force('charge').strength(-900);
    Graph.d3Force('link').distance(l => l.is_close ? 180 : 130);
    Graph.d3VelocityDecay(0.25);
    Graph.d3AlphaDecay(0.02);
    setTimeout(() => Graph.zoomToFit(600, 80), 3500);

    Graph.controls().autoRotate      = true;
    Graph.controls().autoRotateSpeed = 0.35;

    setTimeout(() => {{ document.getElementById('hint').style.opacity = '0'; }}, 5000);
  </script>
</body>
</html>"""


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    df = _load()

    embed_path = os.path.join(ASSETS_DIR, "social_3d.html")
    with open(embed_path, "w", encoding="utf-8") as fh:
        fh.write(_build_3d_html(df))

    n_close = int(df["in_close_friends"].sum()) if not df.empty and "in_close_friends" in df.columns else 0
    n_total = len(df)
    n_msgs  = int(df["message_count"].sum())    if not df.empty and "message_count"    in df.columns else 0

    if not df.empty and {"label", "message_count"}.issubset(df.columns):
        table_data = (
            df[["label", "message_count"]]
            .rename(columns={"label": "Pseudo", "message_count": "Messages"})
            .sort_values("Messages", ascending=False)
            .to_dict("records")
        )
    else:
        table_data = []

    return html.Div(
        style={"paddingTop": "64px", "minHeight": "100vh", "background": "var(--bg-base)"},
        children=[

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

            html.Div(
                style={"padding": "0 48px 24px"},
                children=[
                    html.Iframe(
                        src="/assets/social_3d.html",
                        style={
                            "width": "100%",
                            "height": "720px",
                            "border": "none",
                            "borderRadius": "16px",
                            "overflow": "hidden",
                            "display": "block",
                        },
                    )
                ],
            ),

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
                            {"name": "Pseudo",   "id": "Pseudo",   "type": "text"},
                            {"name": "Messages", "id": "Messages", "type": "numeric"},
                        ],
                        data=table_data,
                        sort_action="native",
                        filter_action="native",
                        page_size=15,
                        style_table={
                            "borderRadius": "12px", "overflow": "hidden",
                            "border": "1px solid rgba(255,255,255,0.08)",
                        },
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
                        style_data_conditional=[{
                            "if": {"state": "active"},
                            "backgroundColor": "rgba(109,94,245,0.2)",
                            "border": "1px solid var(--accent-primary)",
                        }],
                    ),
                ],
            ),
        ],
    )
