import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

PAGES = [
    {"label": "Home",     "href": "/",             "icon": "tabler:home"},
    {"label": "Timeline", "href": "/timeline",      "icon": "tabler:timeline"},
    {"label": "Social",   "href": "/social",        "icon": "tabler:network"},
    {"label": "Photos",   "href": "/photos",        "icon": "tabler:camera"},
    {"label": "Clusters", "href": "/clusters",      "icon": "tabler:circles"},
    {"label": "Netflix",  "href": "/netflix",       "icon": "tabler:movie"},
    {"label": "Spotify",  "href": "/spotify",       "icon": "tabler:music"},
    {"label": "Album",    "href": "/memory-album",  "icon": "tabler:heart"},
    {"label": "Analyse",  "href": "/psy",           "icon": "tabler:brain"},
]


def create_navbar(current_path: str = "/") -> html.Nav:
    links = []
    for page in PAGES:
        is_active = page["href"] == current_path
        links.append(
            dcc.Link(
                href=page["href"],
                style={"textDecoration": "none"},
                children=dmc.NavLink(
                    label=page["label"],
                    leftSection=DashIconify(icon=page["icon"], width=18),
                    active=is_active,
                    variant="subtle",
                    color="violet",
                    # Pas de styles inline sur color/background — géré par CSS
                    # pour que les états :hover/:active fonctionnent en dark mode
                    className=f"nav-item {'nav-item-active' if is_active else ''}",
                ),
            )
        )

    window_controls = html.Div(
        className="mac-controls",
        children=[
            html.Div(className="mac-btn close"),
            html.Div(className="mac-btn minimize"),
            html.Div(className="mac-btn maximize"),
        ],
    )

    return html.Nav(
        className="navbar",
        children=[
            window_controls,
            html.Div(className="navbar-links", children=links),
        ],
    )
