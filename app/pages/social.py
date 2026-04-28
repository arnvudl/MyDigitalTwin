import glob
import html as html_lib
import json
import os
import re
from collections import Counter
from datetime import datetime
from functools import lru_cache

import pandas as pd
from dash import html, dash_table
from config import INSTAGRAM_INBOX, INSTAGRAM_SENDER_NAME, SOCIAL_GRAPH_DIR

# ─── PATHS ───────────────────────────────────────────────────────────────────
SOCIAL_DIR = SOCIAL_GRAPH_DIR

_HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(_HERE, "..", "assets")
INBOX = INSTAGRAM_INBOX


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
@lru_cache(maxsize=1)
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


@lru_cache(maxsize=100)
def _conv_stats(node_id: str, my_name: str = INSTAGRAM_SENDER_NAME or "A R N A U D") -> dict:
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
_TEMPLATE_PATH = os.path.join(ASSETS_DIR, "social_3d_template.html")

def _build_3d_html(df: pd.DataFrame, stats_map: dict) -> str:
    data_json = json.dumps(_df_to_graph_data(df, stats_map))
    with open(_TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read().replace("__GRAPH_DATA__", data_json)



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
                    html.P("Détail des interactions",
                           className="section-label",
                           style={"marginBottom": "20px"}),
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

