"""Icon helper — vraies icônes SVG via DashIconify (Tabler Icons)."""
from dash_iconify import DashIconify


def icon(name: str, size: int = 22, color: str = "currentColor") -> DashIconify:
    """Retourne une icône Tabler SVG.

    Usage : icon("tabler:music"), icon("tabler:search", size=18)
    Catalogue : https://icon-sets.iconify.design/tabler/
    """
    return DashIconify(icon=name, width=size, height=size, color=color)


# ─── Icônes Tabler (SVG vectoriel) ───────────────────────────────────────────
MUSIC    = "tabler:music"
CLOCK    = "tabler:clock"
MIC      = "tabler:microphone"
FILM     = "tabler:movie"
TV       = "tabler:device-tv"
VIDEO    = "tabler:video"
SEARCH   = "tabler:search"
TWITTER  = "tabler:brand-x"
PHONE    = "tabler:device-mobile"
FOLDER   = "tabler:folder"
IMAGE    = "tabler:photo"
PUZZLE   = "tabler:puzzle"
TARGET   = "tabler:target"
CHAT     = "tabler:message"
BOX      = "tabler:package"
STAR     = "tabler:star"
HEART    = "tabler:heart"
CHART    = "tabler:chart-bar"
USER     = "tabler:user"
NETWORK  = "tabler:network"
BRAIN    = "tabler:brain"
TIMELINE = "tabler:timeline"
ALBUM    = "tabler:photo-album"
CLUSTER  = "tabler:circles"


# ─── Compat shim : svg_icon() utilisé dans certaines pages ───────────────────
def svg_icon(name: str, size: str = "22") -> DashIconify:
    """Alias de compatibilité pour l'ancien `svg_icon(EMOJI, size)`.

    Accepte désormais un nom d'icône Tabler au lieu d'un emoji.
    """
    return icon(name, size=int(size))
