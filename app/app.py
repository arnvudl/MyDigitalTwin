import threading
import dash
from dash import Input, Output, callback, dcc, html

from app.components import create_navbar
from app.pages import home, clusters, netflix, spotify, social, timeline, psy, photos, clone, inventory


def _prewarm_caches():
    """Load all heavy data at startup so first page visits are instant."""
    try: home.load_interest_profiles()
    except Exception: pass
    try: home.load_all_keywords()
    except Exception: pass
    try: home.compute_stats()
    except Exception: pass
    try: spotify._load_spotify()
    except Exception: pass
    try: netflix._load_netflix()
    except Exception: pass
    try: social._load()
    except Exception: pass
    try: photos._read_clusters()
    except Exception: pass


threading.Thread(target=_prewarm_caches, daemon=True).start()

# ─── APP INIT ─────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    title="MyDigitalTwin",
)
server = app.server

# ─── ROUTE FLASK — SERVIR LES PHOTOS ─────────────────────────────────────────
import os as _os
from flask import send_file as _send_file, abort as _abort

_DATA_ROOT = "/app/data" if _os.path.exists("/app/data") else "data"

@server.route("/photo/<path:filepath>")
def serve_photo(filepath):
    full_path = _os.path.join(_DATA_ROOT, filepath)
    if not _os.path.isfile(full_path):
        _abort(404)
    return _send_file(full_path)

# ─── ROOT LAYOUT ──────────────────────────────────────────────────────────────
app.layout = html.Div(
    children=[
        dcc.Location(id="url", refresh=False),
        html.Div(id="navbar-container"),
        html.Div(id="page-content"),
    ]
)


# ─── ROUTING ──────────────────────────────────────────────────────────────────
@callback(
    Output("page-content", "children"),
    Output("navbar-container", "children"),
    Input("url", "pathname"),
)
def display_page(pathname):
    pathname = pathname or "/"

    navbar = create_navbar(current_path=pathname)

    if pathname == "/":
        return home.layout(), navbar

    if pathname == "/topology":
        return clusters.layout(), navbar

    if pathname == "/netflix":
        return netflix.layout(), navbar

    if pathname == "/spotify":
        return spotify.layout(), navbar

    if pathname == "/social":
        return social.layout(), navbar

    if pathname == "/timeline":
        return timeline.layout(), navbar

    if pathname == "/psy":
        return psy.layout(), navbar

    if pathname == "/photos":
        return photos.layout(), navbar

    if pathname == "/clone":
        return clone.layout(), navbar

    if pathname == "/inventaire":
        return inventory.layout(), navbar

    # 404
    return html.Div("404 — Page introuvable",
                    style={"color": "var(--text-muted)", "padding": "100px", "textAlign": "center"}), navbar


# ─── HOME TAG CLICK ───────────────────────────────────────────────────────────
from dash import ALL


@callback(
    Output("home-selected-tag", "data"),
    Input({"type": "orbit-tag", "index": ALL}, "n_clicks"),
    Input({"type": "orbit-tag", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def on_tag_click(n_clicks_list, ids):
    from dash import ctx
    if not ctx.triggered_id:
        return dash.no_update
    triggered = ctx.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "orbit-tag":
        return triggered["index"]
    return dash.no_update


# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # app.run(debug=True)
    # Exposer sur 0.0.0.0 pour Docker
    app.run(host="0.0.0.0", port=8050, debug=True)
