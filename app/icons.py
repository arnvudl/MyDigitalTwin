"""Icon helper — emoji avec fontSize géré via html.Span."""
from dash import html


def svg_icon(emoji: str, size: str = "22") -> html.Span:
    return html.Span(emoji, style={"fontSize": f"{size}px", "lineHeight": "1"})


# ─── Emojis visuels (affichage dashboard) ────────────────────────────────────
MUSIC   = "🎵"
CLOCK   = "⏱"
MIC     = "🎤"
FILM    = "🎬"
TV      = "📺"
VIDEO   = "🎥"
SEARCH  = "🔍"
TWITTER = "𝕏"
PHONE   = "📱"
FOLDER  = "📂"
IMAGE   = "🖼"
PUZZLE  = "🧩"
TARGET  = "🎯"
CHAT    = "💬"
BOX     = "📦"
