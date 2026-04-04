from dash import html, dcc

PAGES = [
    {"label": "🏠 Home", "href": "/"},
    {"label": "🎬 Netflix", "href": "/netflix"},
    {"label": "🎵 Spotify", "href": "/spotify"},
    {"label": "🎯 Recommandations", "href": "/recommandations"},
    {"label": "🤖 Clone", "href": "/clone"},
    {"label": "📅 Timeline", "href": "/timeline"},
    {"label": "🕸️ Social", "href": "/social"},
    {"label": "🖼️ Photos", "href": "/photos"},
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

    return html.Nav(
        className="navbar",
        children=[
            dcc.Link(
                [
                    "MyDigitalTwin",
                    html.Span("v1.0"),
                ],
                href="/",
                className="navbar-brand",
            ),
            html.Div(className="navbar-links", children=links),
            html.Div(className="navbar-dot"),
        ],
    )
