"""
build_music_library.py — Spotify Playlist → music_library.json + LLM prompt

Récupère les titres d'une playlist Spotify et génère :
  1. data/LLM_DATA/music_library.json   — structure exploitable par 03_music_matching.ipynb
  2. Un prompt prêt-à-l'emploi pour Gemini/Claude afin de remplir les "moment tags"

Usage :
    python src/scripts/03_memory_album/build_music_library.py

Prérequis :
    pip install spotipy
    .env : SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
    config.yaml : memory_album.spotify_playlist_id (ex: "37i9dQZF1DX...")

Sortie music_library.json :
    [
      {
        "track_id"       : "spotify:track:4x6jx7AeSyE7PlQTdCjIJs",
        "track_name"     : "LEÇONS",
        "artist"         : "Damso",
        "album"          : "QALF infinity",
        "album_cover_url": "https://i.scdn.co/image/...",
        "moments"        : []    ← à remplir avec le LLM
      },
      ...
    ]
"""

import sys
import os
import json

# ── Localiser config.py ──────────────────────────────────────────────────────
_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(os.path.dirname(_d), 'config.py')):
    _parent = os.path.dirname(os.path.dirname(_d))
    if _parent == _d:
        raise RuntimeError("config.py introuvable")
    _d = _parent
PROJECT_ROOT = os.path.dirname(_d) if os.path.exists(os.path.join(os.path.dirname(_d), 'config.py')) else _d

# Remonter jusqu'à trouver config.py au même niveau
_root = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_root, 'config.py')):
    _parent = os.path.dirname(_root)
    if _parent == _root:
        raise RuntimeError("config.py introuvable")
    _root = _parent

sys.path.insert(0, _root)

import yaml
from config import MUSIC_LIBRARY_PATH, LLM_DATA

# ── Lecture config ────────────────────────────────────────────────────────────
_cfg_path = os.path.join(_root, 'config.yaml')
with open(_cfg_path, encoding='utf-8') as _f:
    _cfg = yaml.safe_load(_f)

_ma = _cfg.get('memory_album', {})
PLAYLIST_ID = _ma.get('spotify_playlist_id', '').strip()

if not PLAYLIST_ID:
    print(
        "⚠  config.yaml → memory_album.spotify_playlist_id est vide.\n"
        "   Renseigne l'ID de ta playlist Spotify, ex:\n"
        "   https://open.spotify.com/playlist/37i9dQZF1DX... → ID = 37i9dQZF1DX...\n"
        "   Puis relance ce script."
    )
    sys.exit(1)

# ── Spotipy ──────────────────────────────────────────────────────────────────
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    print("❌ spotipy non installé. Lance : pip install spotipy")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, '.env'))

CLIENT_ID     = os.getenv('SPOTIFY_CLIENT_ID', '')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', '')

if not CLIENT_ID or not CLIENT_SECRET:
    print(
        "❌ SPOTIFY_CLIENT_ID ou SPOTIFY_CLIENT_SECRET manquants.\n"
        "   Ajoute-les dans ton fichier .env."
    )
    sys.exit(1)

# SpotifyOAuth requis depuis fin 2024 même pour les playlists publiques.
# Premier lancement : affiche une URL à ouvrir dans le navigateur,
# puis demande de coller l'URL de redirection.
# Les lancements suivants utilisent le cache .cache (token auto-rafraîchi).
auth_manager = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri='http://127.0.0.1:8888/callback',
    scope='playlist-read-private playlist-read-collaborative',
    open_browser=False,
    cache_path=os.path.join(_root, '.spotify_cache'),
)
sp = spotipy.Spotify(auth_manager=auth_manager)

# ── Récupération playlist ─────────────────────────────────────────────────────
print(f"Récupération playlist : {PLAYLIST_ID} ...")

tracks = []
offset = 0
limit  = 100

while True:
    response = sp.playlist_tracks(
        PLAYLIST_ID,
        offset=offset,
        limit=limit,
    )
    items = response.get('items', [])
    if not items:
        break

    for item in items:
        # Spotify a changé la clé 'track' → 'item' dans playlist_items
        t = item.get('track') or item.get('item')
        if t is None or t.get('id') is None:
            continue

        artist_names = ', '.join(a['name'] for a in t.get('artists', []))
        images       = t.get('album', {}).get('images', [])
        cover_url    = images[0]['url'] if images else ''

        tracks.append({
            'track_id'       : f"spotify:track:{t['id']}",
            'track_name'     : t['name'],
            'artist'         : artist_names,
            'album'          : t.get('album', {}).get('name', ''),
            'album_cover_url': cover_url,
            'moments'        : [],   # à remplir via LLM (voir prompt ci-dessous)
        })

    if response.get('next') is None:
        break
    offset += limit

print(f"{len(tracks)} titres récupérés")

# ── Merge avec library existante (préserver les moments déjà remplis) ─────────
existing = {}
if os.path.exists(MUSIC_LIBRARY_PATH):
    with open(MUSIC_LIBRARY_PATH, encoding='utf-8') as _f:
        for entry in json.load(_f):
            existing[entry['track_id']] = entry.get('moments', [])
    print(f"Merge avec {len(existing)} entrées existantes (conservation des moments)")

for t in tracks:
    if t['track_id'] in existing and existing[t['track_id']]:
        t['moments'] = existing[t['track_id']]

# ── Écriture JSON ─────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(MUSIC_LIBRARY_PATH), exist_ok=True)
with open(MUSIC_LIBRARY_PATH, 'w', encoding='utf-8') as _f:
    json.dump(tracks, _f, ensure_ascii=False, indent=2)

print(f"✓ music_library.json → {MUSIC_LIBRARY_PATH}")

# ── Prompt LLM ────────────────────────────────────────────────────────────────
# Génère un prompt prêt-à-l'emploi pour Gemini/Claude
# pour remplir le champ "moments" de chaque titre.
# L'utilisateur copie ce prompt, envoie à son LLM, puis colle la réponse JSON
# pour mettre à jour music_library.json.

tracks_without_moments = [t for t in tracks if not t['moments']]

if not tracks_without_moments:
    print("\n✅ Tous les titres ont déjà des moment tags — aucun prompt nécessaire.")
else:
    print(f"\n{len(tracks_without_moments)} titres sans moment tags.")

    # Liste compacte pour le prompt
    track_list_str = '\n'.join(
        f'  - track_id: "{t["track_id"]}", title: "{t["track_name"]}", artist: "{t["artist"]}"'
        for t in tracks_without_moments
    )

    prompt = f"""Tu es un assistant musical expert. Pour chaque titre ci-dessous, génère une liste de 3 à 6 **moment tags** en anglais qui décrivent le contexte émotionnel ou situationnel idéal pour écouter ce titre.

Les moment tags doivent être courts (3-5 mots), évocateurs, et utiles pour associer une chanson à des photos de vie. Exemples de bons moment tags :
- "late night drive", "summer vibes", "chill at home", "party with friends", "melancholy rain", "morning run", "sunset road trip"

Mentionner le type de lieu (urbain, montagne, plage) + le nombres de personne + le cadre de la photo + l'heure (nuit, jour, lever du soleil) peut beaucoup aider également.

Réponds UNIQUEMENT avec un objet JSON valide de la forme :
{{
  "spotify:track:ID1": ["tag1", "tag2", "tag3"],
  "spotify:track:ID2": ["tag1", "tag2"],
  ...
}}

Titres à taguer :
{track_list_str}
"""

    PROMPT_PATH = os.path.join(LLM_DATA, 'music_moments_prompt.txt')
    os.makedirs(LLM_DATA, exist_ok=True)
    with open(PROMPT_PATH, 'w', encoding='utf-8') as _f:
        _f.write(prompt)

    print(f"✓ Prompt LLM → {PROMPT_PATH}")
    print()
    print("─" * 60)
    print("PROCHAINE ÉTAPE :")
    print("  1. Ouvre le fichier :", PROMPT_PATH)
    print("  2. Copie-colle le contenu dans Gemini ou Claude")
    print("  3. Copie la réponse JSON")
    print("  4. Lance :")
    print("     python src/scripts/03_memory_album/apply_moment_tags.py <fichier_reponse.json>")
    print("─" * 60)
