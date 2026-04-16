import glob
import html as html_lib
import json
import os
import re
from collections import Counter
from datetime import datetime

import pandas as pd
from dash import html, dash_table

# ─── PATHS ───────────────────────────────────────────────────────────────────
WAREHOUSE   = "/app/data/warehouse" if os.path.exists("/app/data/warehouse") else "warehouse"
SOCIAL_DIR  = os.path.join(WAREHOUSE, "social_graph")

_HERE      = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(_HERE, "..", "assets")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))  # pages -> app -> project root

if os.path.exists("/app/data"):
    INBOX = "/app/data/raw/INSTAGRAM/your_instagram_activity/messages/inbox"
else:
    INBOX = os.path.join(_PROJECT_ROOT, "data", "raw", "INSTAGRAM",
                         "your_instagram_activity", "messages", "inbox")


_NOISE = re.compile(
    r"envoy[eé].*pi[eè]ce jointe"
    r"|r[eé]pondu [àa] votre story"
    r"|r[eé]agi [àa] votre message"
    r"|reacted .* to your message"
    r"|liked a message"
    r"|started an audio call"
    r"|audio call ended"
    r"|missed an audio call"
    r"|appel (manqu[eé]|termin[eé]|vid[eé]o)"
    r"|set (the|your) nickname"
    r"|0 replies 0 retweets 0 likes"
    r"|view post on instagram"
    r"|a partag[eé] une publication"
    r"|partag[eé] un profil",
    re.IGNORECASE,
)


def _fix_encoding(text: str) -> str:
    """Fix Instagram mojibake: JSON was stored as latin-1 bytes decoded as UTF-8."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


MONTH_FR = {
    1:"jan",2:"fév",3:"mar",4:"avr",5:"mai",6:"jun",
    7:"jul",8:"aoû",9:"sep",10:"oct",11:"nov",12:"déc",
}

# ─── DATA ────────────────────────────────────────────────────────────────────
def _load():
    """Lit social_graph depuis le dossier parquet (cohérent avec les autres tables warehouse)."""
    if not os.path.exists(SOCIAL_DIR):
        return pd.DataFrame()
    files = [
        os.path.join(SOCIAL_DIR, f)
        for f in os.listdir(SOCIAL_DIR)
        if f.endswith(".parquet") and not f.startswith(".")
    ]
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def _conv_stats(node_id: str, my_name: str = "A R N A U D") -> dict:
    """Load conversation stats from raw Instagram JSON files."""
    folder = os.path.join(INBOX, node_id)
    if not os.path.isdir(folder):
        return {}

    messages = []
    for jf in sorted(glob.glob(os.path.join(folder, "message_*.json"))):
        try:
            with open(jf, encoding="utf-8") as f:
                d = json.load(f)
            for m in d.get("messages", []):
                if "content" in m:
                    m["content"] = _fix_encoding(m["content"])
                if "sender_name" in m:
                    m["sender_name"] = _fix_encoding(m["sender_name"])
            messages.extend(d.get("messages", []))
        except Exception:
            pass

    my_name_fixed = _fix_encoding(my_name)

    if not messages:
        return {}

    messages.sort(key=lambda m: m.get("timestamp_ms", 0))

    first_dt = datetime.fromtimestamp(messages[0]["timestamp_ms"] / 1000)
    last_dt  = datetime.fromtimestamp(messages[-1]["timestamp_ms"] / 1000)

    sent     = sum(1 for m in messages if m.get("sender_name") == my_name_fixed)
    received = len(messages) - sent

    # Peak month
    month_counts = Counter(
        datetime.fromtimestamp(m["timestamp_ms"] / 1000).strftime("%Y-%m")
        for m in messages if m.get("timestamp_ms")
    )
    peak_ym, peak_count = month_counts.most_common(1)[0] if month_counts else ("", 0)
    if peak_ym:
        y, mo = peak_ym.split("-")
        peak_label = f"{MONTH_FR[int(mo)]} {y}"
    else:
        peak_label = "—"

    # Recent text messages — skip noise and media-only entries
    recent = []
    for m in reversed(messages):
        content = m.get("content", "")
        if not content or len(content) > 300:
            continue
        if _NOISE.search(content):
            continue
        sender = m.get("sender_name", "")
        ts = datetime.fromtimestamp(m["timestamp_ms"] / 1000).strftime("%d %b %Y")
        recent.append({
            "sender": sender,
            "is_me": sender == my_name_fixed,
            "text": html_lib.escape(content[:120]),
            "date": ts,
        })
        if len(recent) >= 4:
            break

    return {
        "first": first_dt.strftime("%d %b %Y"),
        "last":  last_dt.strftime("%d %b %Y"),
        "sent":     sent,
        "received": received,
        "peak":     peak_label,
        "peak_count": peak_count,
        "recent": recent,
    }


def _df_to_graph_data(df: pd.DataFrame, stats_map: dict) -> dict:
    nodes = [{"id": "arnaud", "label": "Arnaud", "is_close": False, "msg_count": 0, "val": 80, "stats": {}}]
    links = []

    if df.empty:
        return {"nodes": nodes, "links": links}

    w_max = df["message_count"].max()

    for _, row in df.iterrows():
        node_id   = str(row["node_id"])
        label     = str(row["label"])
        msg_count = int(row["message_count"])
        is_close  = bool(row["in_close_friends"])
        ratio = msg_count / w_max
        if is_close:
            val = int(20 + 44 * ratio)
        else:
            val = int(1  + 11 * ratio)

        nodes.append({
            "id": node_id, "label": label,
            "is_close": is_close, "msg_count": msg_count, "val": val,
            "stats": stats_map.get(node_id, {}),
        })
        links.append({
            "source": "arnaud", "target": node_id,
            "is_close": is_close,
            "width": 0.8 + int(2 * ratio),
        })

    return {"nodes": nodes, "links": links}


# ─── 3D HTML GENERATOR ───────────────────────────────────────────────────────
def _build_3d_html(df: pd.DataFrame, stats_map: dict) -> str:
    data_json = json.dumps(_df_to_graph_data(df, stats_map))

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

    /* ── Search bar ── */
    #search-wrap {{
      position:fixed; top:18px; left:50%; transform:translateX(-50%);
      z-index:300; width:260px;
    }}
    #search-input {{
      width:100%; padding:9px 36px 9px 14px;
      background:rgba(10,7,26,.78);
      backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px);
      border:1px solid rgba(168,85,247,.25); border-radius:30px;
      color:#fff; font-size:13px; font-family:inherit; outline:none;
      box-shadow:0 4px 20px rgba(0,0,0,.4);
      transition:border-color .2s, box-shadow .2s;
    }}
    #search-input::placeholder {{ color:rgba(255,255,255,.3); }}
    #search-input:focus {{
      border-color:rgba(168,85,247,.6);
      box-shadow:0 4px 24px rgba(168,85,247,.2);
    }}
    #search-clear {{
      position:absolute; right:11px; top:50%; transform:translateY(-50%);
      background:none; border:none; color:rgba(255,255,255,.3);
      cursor:pointer; font-size:13px; padding:2px 4px; display:none;
    }}
    #search-clear:hover {{ color:rgba(255,255,255,.7); }}
    #search-results {{
      margin-top:6px; background:rgba(10,7,26,.92);
      backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px);
      border:1px solid rgba(168,85,247,.18); border-radius:14px;
      overflow:hidden; display:none;
      box-shadow:0 8px 32px rgba(0,0,0,.5);
    }}
    .sr-item {{
      padding:10px 16px; cursor:pointer; display:flex;
      align-items:center; gap:10px;
      transition:background .15s;
      border-bottom:1px solid rgba(255,255,255,.04);
    }}
    .sr-item:last-child {{ border-bottom:none; }}
    .sr-item:hover {{ background:rgba(168,85,247,.12); }}
    .sr-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
    .sr-name {{ font-size:13px; color:#e0d8ff; font-weight:500; flex:1; }}
    .sr-msgs {{ font-size:11px; color:rgba(255,255,255,.3); }}
    .sr-empty {{ padding:12px 16px; font-size:13px; color:rgba(255,255,255,.3); text-align:center; }}

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

    /* ── Detail panel (slide-in from right on click) ── */
    #detail {{
      position:fixed; top:0; right:0; bottom:0; width:320px;
      background:rgba(8,5,22,0.88);
      backdrop-filter:blur(32px) saturate(160%);
      -webkit-backdrop-filter:blur(32px) saturate(160%);
      border-left:1px solid rgba(168,85,247,0.18);
      padding:28px 24px; overflow-y:auto;
      transform:translateX(100%);
      transition:transform .35s cubic-bezier(.16,1,.3,1);
      z-index:200;
      display:flex; flex-direction:column; gap:20px;
    }}
    #detail.open {{ transform:translateX(0); }}
    #detail-close {{
      position:absolute; top:16px; right:16px;
      width:28px; height:28px; border-radius:50%;
      background:rgba(255,255,255,.07); border:none;
      color:rgba(255,255,255,.5); cursor:pointer; font-size:14px;
      display:flex; align-items:center; justify-content:center;
      transition:background .2s;
    }}
    #detail-close:hover {{ background:rgba(255,255,255,.14); color:#fff; }}
    #detail-name {{
      font-size:20px; font-weight:700; color:#ede8ff; padding-right:32px;
      line-height:1.2;
    }}
    #detail-badge {{
      display:inline-block; font-size:10px; font-weight:700;
      letter-spacing:.8px; text-transform:uppercase;
      padding:3px 10px; border-radius:20px;
    }}
    #detail-badge.cf  {{ background:rgba(168,85,247,.22); color:#c084fc; }}
    #detail-badge.fol {{ background:rgba(59,79,160,.22);  color:#93a8d4; }}
    .d-section {{ display:flex; flex-direction:column; gap:10px; }}
    .d-label {{
      font-size:10px; font-weight:700; letter-spacing:1.5px;
      text-transform:uppercase; color:rgba(255,255,255,.3);
      margin-bottom:2px;
    }}
    .d-row {{
      display:flex; justify-content:space-between; align-items:center;
      padding:10px 14px; border-radius:10px;
      background:rgba(255,255,255,.04);
      border:1px solid rgba(255,255,255,.06);
    }}
    .d-row-key {{ font-size:12px; color:rgba(255,255,255,.45); }}
    .d-row-val {{ font-size:13px; font-weight:600; color:#e0d8ff; }}
    .msg-bubble {{
      padding:10px 13px; border-radius:12px;
      font-size:12px; line-height:1.5; max-width:100%;
    }}
    .msg-bubble.me {{
      background:rgba(168,85,247,.18);
      border:1px solid rgba(168,85,247,.22);
      color:#ddd6ff; align-self:flex-end; border-bottom-right-radius:3px;
    }}
    .msg-bubble.them {{
      background:rgba(255,255,255,.06);
      border:1px solid rgba(255,255,255,.08);
      color:rgba(255,255,255,.7); border-bottom-left-radius:3px;
    }}
    .msg-date {{ font-size:10px; color:rgba(255,255,255,.25); margin-top:4px; }}
    .msgs-wrap {{ display:flex; flex-direction:column; gap:8px; }}
    #detail-sep {{
      height:1px; background:rgba(255,255,255,.06); border:none; margin:0;
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

  <!-- Search -->
  <div id="search-wrap">
    <input id="search-input" type="text" placeholder="Rechercher une personne…" autocomplete="off"/>
    <button id="search-clear">✕</button>
    <div id="search-results"></div>
  </div>

  <!-- Hint -->
  <div id="hint">Drag to orbit &nbsp;·&nbsp; Scroll to zoom &nbsp;·&nbsp; Click for details</div>

  <!-- Detail panel -->
  <div id="detail">
    <button id="detail-close" onclick="closeDetail()">✕</button>
    <div id="detail-name">—</div>
    <div id="detail-badge" class="cf">⭐ Close Friend</div>
    <hr id="detail-sep"/>
    <div id="detail-stats" class="d-section"></div>
    <div id="detail-msgs-section" class="d-section" style="display:none">
      <div class="d-label">Messages récents</div>
      <div id="detail-msgs" class="msgs-wrap"></div>
    </div>
  </div>

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
        // Camera zoom
        const len = Math.hypot(node.x||.01, node.y||.01, node.z||.01);
        Graph.cameraPosition(
          {{ x: node.x*(len+150)/len, y: node.y*(len+150)/len, z: node.z*(len+150)/len }},
          node, 900
        );
        if (node.id === 'arnaud') {{ closeDetail(); return; }}
        openDetail(node);
      }})
      .onBackgroundClick(() => {{
        Graph.cameraPosition({{x:0, y:0, z:500}}, {{x:0,y:0,z:0}}, 800);
        closeDetail();
      }});

    Graph.d3Force('charge').strength(-900);
    Graph.d3Force('link').distance(l => l.is_close ? 180 : 130);
    Graph.d3VelocityDecay(0.25);
    Graph.d3AlphaDecay(0.02);
    setTimeout(() => Graph.zoomToFit(600, 80), 3500);

    Graph.controls().autoRotate      = true;
    Graph.controls().autoRotateSpeed = 0.35;

    setTimeout(() => {{ document.getElementById('hint').style.opacity = '0'; }}, 5000);

    // ── Search ──────────────────────────────────────────────────────────────
    const searchInput   = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const searchClear   = document.getElementById('search-clear');
    const allNodes      = graphData.nodes.filter(n => n.id !== 'arnaud');

    function runSearch(q) {{
      searchResults.innerHTML = '';
      if (!q) {{ searchResults.style.display = 'none'; searchClear.style.display = 'none'; return; }}
      searchClear.style.display = 'block';
      const hits = allNodes
        .filter(n => n.label.toLowerCase().includes(q.toLowerCase()))
        .sort((a, b) => b.msg_count - a.msg_count)
        .slice(0, 8);
      if (!hits.length) {{
        searchResults.innerHTML = '<div class="sr-empty">Aucun résultat</div>';
        searchResults.style.display = 'block';
        return;
      }}
      hits.forEach(n => {{
        const item = document.createElement('div');
        item.className = 'sr-item';
        item.innerHTML = `
          <div class="sr-dot" style="background:${{n.is_close ? '#a855f7' : '#3b4fa0'}};
            ${{n.is_close ? 'box-shadow:0 0 5px rgba(168,85,247,.8)' : ''}}"></div>
          <span class="sr-name">${{n.label}}</span>
          <span class="sr-msgs">${{n.msg_count.toLocaleString()}} msgs</span>
        `;
        item.addEventListener('click', () => {{
          closeSearch();
          // Zoom to node
          const obj = Graph.graphData().nodes.find(x => x.id === n.id);
          if (obj) {{
            const len = Math.hypot(obj.x||.01, obj.y||.01, obj.z||.01);
            Graph.cameraPosition(
              {{ x: obj.x*(len+150)/len, y: obj.y*(len+150)/len, z: obj.z*(len+150)/len }},
              obj, 900
            );
            openDetail(n);
          }}
        }});
        searchResults.appendChild(item);
      }});
      searchResults.style.display = 'block';
    }}

    function closeSearch() {{
      searchInput.value = '';
      searchResults.style.display = 'none';
      searchClear.style.display = 'none';
    }}

    searchInput.addEventListener('input', e => runSearch(e.target.value.trim()));
    searchClear.addEventListener('click', closeSearch);
    document.addEventListener('click', e => {{
      if (!document.getElementById('search-wrap').contains(e.target)) {{
        searchResults.style.display = 'none';
      }}
    }});

    // ── Detail panel ────────────────────────────────────────────────────────
    function closeDetail() {{
      document.getElementById('detail').classList.remove('open');
    }}

    function openDetail(node) {{
      const s = node.stats || {{}};
      const cf = node.is_close;

      document.getElementById('detail-name').textContent = node.label;
      const badge = document.getElementById('detail-badge');
      badge.textContent = cf ? '⭐ Close Friend' : 'Follower';
      badge.className   = 'detail-badge ' + (cf ? 'cf' : 'fol');

      // Stats rows
      const statsEl = document.getElementById('detail-stats');
      statsEl.innerHTML = '';
      const rows = [
        ['💬 Messages', node.msg_count.toLocaleString()],
        ['📤 Envoyés',  s.sent   != null ? s.sent.toLocaleString()     : '—'],
        ['📥 Reçus',    s.received != null ? s.received.toLocaleString() : '—'],
        ['📅 Première conv', s.first || '—'],
        ['🕐 Dernière conv', s.last  || '—'],
        ['\U0001F525 Pic activit\u00e9', s.peak ? s.peak + ' (' + (s.peak_count||0).toLocaleString() + ' msgs)' : '\u2014'],
      ];
      rows.forEach(([k, v]) => {{
        const row = document.createElement('div');
        row.className = 'd-row';
        row.innerHTML = `<span class="d-row-key">${{k}}</span><span class="d-row-val">${{v}}</span>`;
        statsEl.appendChild(row);
      }});

      // Recent messages
      const msgsSection = document.getElementById('detail-msgs-section');
      const msgsEl      = document.getElementById('detail-msgs');
      msgsEl.innerHTML  = '';
      const recent = s.recent || [];
      if (recent.length > 0) {{
        msgsSection.style.display = 'flex';
        recent.forEach(m => {{
          const wrap = document.createElement('div');
          wrap.innerHTML = `
            <div class="msg-bubble ${{m.is_me ? 'me' : 'them'}}">${{m.text}}</div>
            <div class="msg-date" style="text-align:${{m.is_me ? 'right' : 'left'}}">${{m.date}}</div>
          `;
          msgsEl.appendChild(wrap);
        }});
      }} else {{
        msgsSection.style.display = 'none';
      }}

      document.getElementById('detail').classList.add('open');
    }}
  </script>
</body>
</html>"""


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    df = _load()

    # Pre-compute conversation stats for each node
    stats_map = {}
    if not df.empty and os.path.isdir(INBOX):
        for node_id in df["node_id"].astype(str):
            s = _conv_stats(node_id)
            if s:
                stats_map[node_id] = s

    embed_path = os.path.join(ASSETS_DIR, "social_3d.html")
    with open(embed_path, "w", encoding="utf-8") as fh:
        fh.write(_build_3d_html(df, stats_map))

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

    return html.Div(className="page-wrapper", children=[
        html.Div(
            style={"maxWidth": "1100px", "margin": "0 auto", "padding": "40px 32px 80px"},
            children=[

                html.Div(className="home-hero", style={"textAlign": "center"}, children=[
                    html.P("Graphe Social • Instagram", className="home-hero-label"),
                    html.H1(
                        html.Span(["Mon ", html.Em("Réseau")]),
                        className="home-hero-title", style={"fontSize": "56px"},
                    ),
                    html.P(
                        f"{n_total} conversations · {n_close} close friends · {n_msgs:,} messages",
                        className="home-hero-sub",
                    ),
                ]),

                html.Iframe(
                    src="/assets/social_3d.html",
                    style={
                        "width": "100%",
                        "height": "720px",
                        "border": "none",
                        "borderRadius": "20px",
                        "overflow": "hidden",
                        "display": "block",
                        "marginBottom": "40px",
                        "boxShadow": "0 10px 40px rgba(0,0,0,0.5)",
                    },
                ),

                html.Div(style={"marginTop": "8px"}, children=[
                    html.P("Détail des interactions", style={
                        "fontFamily": "var(--font-family)",
                        "fontSize": "11px", "fontWeight": "600",
                        "letterSpacing": "3px", "textTransform": "uppercase",
                        "color": "var(--text-muted)", "marginBottom": "20px",
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
                            "borderRadius": "14px", "overflow": "hidden",
                            "border": "1px solid rgba(255,255,255,0.05)",
                        },
                        style_header={
                            "backgroundColor": "rgba(30,30,30,0.9)",
                            "color": "var(--text-primary)",
                            "fontWeight": "600",
                            "border": "1px solid rgba(255,255,255,0.08)",
                            "padding": "14px 16px",
                            "fontSize": "12px",
                            "letterSpacing": "0.5px",
                            "textTransform": "uppercase",
                        },
                        style_cell={
                            "backgroundColor": "rgba(20,20,20,0.6)",
                            "color": "var(--text-secondary)",
                            "border": "1px solid rgba(255,255,255,0.04)",
                            "padding": "12px 16px",
                            "textAlign": "left",
                            "fontFamily": "var(--font-family)",
                            "fontSize": "14px",
                        },
                        style_data_conditional=[{
                            "if": {"state": "active"},
                            "backgroundColor": "rgba(168,85,247,0.12)",
                            "border": "1px solid rgba(168,85,247,0.3)",
                        }],
                    ),
                ]),
            ],
        ),
    ])
