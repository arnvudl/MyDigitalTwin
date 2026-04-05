from dash import html, dcc

PAGES = [
    {"label": "Home", "href": "/"},
    {"label": "Netflix", "href": "/netflix"},
    {"label": "Spotify", "href": "/spotify"},
    {"label": "Recommandations", "href": "/recommandations"},
    {"label": "Clone", "href": "/clone"},
    {"label": "Timeline", "href": "/timeline"},
    {"label": "Social", "href": "/social"},
    {"label": "Photos", "href": "/photos"},
]

def create_navbar(current_path="/"):
    links = []
    for page in PAGES:
        is_active = page["href"] == current_path
        links.append(
            dcc.Link(
                page["label"],
                href=page["href"],
                className=f"nav-link {'active' if is_active else ''}",
            )
        )

    # Mac-like window controls (red, yellow, green buttons)
    window_controls = html.Div(
        className="mac-controls",
        children=[
            html.Div(className="mac-btn close"),
            html.Div(className="mac-btn minimize"),
            html.Div(className="mac-btn maximize"),
        ]
    )

    return html.Nav(
        className="navbar",
        children=[
            window_controls,
            html.Div(className="navbar-links", children=links),
        ],
    )
