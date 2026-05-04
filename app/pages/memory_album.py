"""
memory_album.py — Page "Memory Album"

Layout vertical style album photo :
  - En-tête global (stats)
  - Pour chaque scène : numéro romain · titre · plage de dates
      → grille photos (lazy load)
      → carte musique (seulement si match réel : temporal / semantic / manual)
      → playlist souvenir dépliable

Perf : _read_delta parse le _delta_log pour n'inclure que les fichiers actifs
       (évite les doublons des anciennes versions Delta).
       Les os.path.isfile() sont faits une seule fois dans _load_album (LRU-cached).
"""

import os
import json
from functools import lru_cache
from urllib.parse import quote

import pandas as pd
import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify
from config import (
    MEMORY_ALBUM_DIR,
    DATA_ROOT,
    SPARK_DATA_ROOT,
    WAREHOUSE,
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
SCENES_DIR      = os.path.join(MEMORY_ALBUM_DIR, 'scenes')
CENTROIDS_DIR   = os.path.join(MEMORY_ALBUM_DIR, 'scene_centroids')
MATCHES_DIR     = os.path.join(MEMORY_ALBUM_DIR, 'music_matches')
PHOTO_MUSIC_DIR = os.path.join(MEMORY_ALBUM_DIR, 'photo_music')
PLAYLISTS_DIR   = os.path.join(MEMORY_ALBUM_DIR, 'group_playlists')

ACCENT        = '#b794f4'
SPOTIFY_GREEN = '#1db954'
# Seuls ces types de match méritent une musique affichée
REAL_MATCH    = {'temporal', 'semantic', 'manual'}


# ─── DATA HELPERS ─────────────────────────────────────────────────────────────

def _spark_to_local(path: str) -> str:
    """Convertit un chemin Spark/Linux vers le chemin local Windows."""
    if path and path.startswith(SPARK_DATA_ROOT):
        return os.path.normpath(DATA_ROOT + path[len(SPARK_DATA_ROOT):])
    return path or ''


def _read_delta(directory: str) -> pd.DataFrame:
    """
    Lit un Delta Lake en parsant _delta_log pour n'inclure QUE les fichiers actifs.
    Sans ça, pandas lirait tous les parquets (y compris les anciennes versions)
    → doublons, triplons, etc.
    """
    if not os.path.exists(directory):
        return pd.DataFrame()

    log_dir = os.path.join(directory, '_delta_log')
    active: set[str] = set()

    if os.path.exists(log_dir):
        for lf in sorted(f for f in os.listdir(log_dir) if f.endswith('.json')):
            try:
                with open(os.path.join(log_dir, lf), encoding='utf-8') as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        act = json.loads(line)
                        if 'add' in act and act['add']:
                            active.add(act['add']['path'])
                        if 'remove' in act and act['remove']:
                            active.discard(act['remove']['path'])
            except Exception:
                continue

        files = [
            os.path.join(directory, p) for p in active
            if os.path.exists(os.path.join(directory, p))
        ]
    else:
        # Fallback sans Delta log (lecture directe)
        files = [
            os.path.join(r, f)
            for r, _, fs in os.walk(directory) if '_delta_log' not in r
            for f in fs if f.endswith('.parquet') and not f.startswith('.')
        ]

    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


@lru_cache(maxsize=1)
def _load_album() -> dict:
    df_matches     = _read_delta(MATCHES_DIR)
    df_centroids   = _read_delta(CENTROIDS_DIR)
    df_scenes      = _read_delta(SCENES_DIR)
    df_photo_music = _read_delta(PHOTO_MUSIC_DIR)
    df_playlists   = _read_delta(PLAYLISTS_DIR)

    if df_centroids.empty:
        return {}

    # ── Merge centroids + music matches ──────────────────────────────────────
    if not df_matches.empty:
        df_merged = df_centroids.merge(
            df_matches[['scene_id', 'track_id', 'track_name', 'artist_name',
                        'match_type', 'album_cover_url']],
            on='scene_id', how='left',
        )
    else:
        df_merged = df_centroids.copy()
        for c in ['track_id', 'track_name', 'artist_name', 'match_type', 'album_cover_url']:
            df_merged[c] = None

    # ── Musique individuelle par photo (matchs réels seulement) ───────────────
    pm_lookup: dict = {}
    if not df_photo_music.empty:
        for _, r in df_photo_music.iterrows():
            if str(r.get('match_type', '')) in REAL_MATCH:
                pm_lookup[r['photo_id']] = {
                    'track_id': r.get('track_id'),
                    'track_name': r.get('track_name', ''),
                    'artist_name': r.get('artist_name', ''),
                    'album_cover_url': r.get('album_cover_url', ''),
                }

    # ── Photos par scène (existence fichier vérifiée ici, pas au rendu) ───────
    photos_by_scene: dict = {}
    if not df_scenes.empty and 'scene_id' in df_scenes.columns:
        sort_cols = [c for c in ['exif_date'] if c in df_scenes.columns]
        for sid, grp in df_scenes.groupby('scene_id'):
            if sort_cols:
                grp = grp.sort_values(sort_cols, na_position='last')
            photos = []
            for _, row in grp.iterrows():
                local = _spark_to_local(row['path'])
                if local and os.path.isfile(local):
                    photos.append({
                        'photo_id': row['photo_id'],
                        'path'    : local,
                        'music'   : pm_lookup.get(row['photo_id']),
                    })
            photos_by_scene[int(sid)] = photos

    # ── Playlists par scène (dédupliquées par track_id) ───────────────────────
    pl_by_scene: dict = {}
    if not df_playlists.empty and 'scene_id' in df_playlists.columns:
        for sid, grp in df_playlists.groupby('scene_id'):
            seen, pl = set(), []
            for _, r in grp.sort_values('rank').iterrows():
                tid = r.get('track_id', '')
                if tid and tid not in seen:
                    seen.add(tid)
                    pl.append(r.to_dict())
            pl_by_scene[int(sid)] = pl

    # ── Tri chronologique ─────────────────────────────────────────────────────
    if 'timestamp_start' in df_merged.columns:
        df_merged = df_merged.sort_values('timestamp_start', na_position='last')

    result = {}
    for _, row in df_merged.iterrows():
        sid     = int(row['scene_id'])
        mt      = str(row.get('match_type') or '')
        is_real = mt in REAL_MATCH
        result[sid] = {
            'scene_id'   : sid,
            'scene_name' : str(row.get('scene_name') or f'Moment {sid}'),
            'photos'     : photos_by_scene.get(sid, []),
            'ts_start'   : row.get('timestamp_start'),
            'ts_end'     : row.get('timestamp_end'),
            'track_id'   : row.get('track_id')                   if is_real else None,
            'track_name' : str(row.get('track_name')  or '')     if is_real else '',
            'artist_name': str(row.get('artist_name') or '')     if is_real else '',
            'cover_url'  : str(row.get('album_cover_url') or '') if is_real else '',
            'playlist'   : pl_by_scene.get(sid, []),
        }
    return result


# ─── URL HELPERS ──────────────────────────────────────────────────────────────

def _photo_url(path: str) -> str:
    norm_path = os.path.normpath(path)
    norm_root = os.path.normpath(DATA_ROOT)
    rel = norm_path[len(norm_root):].lstrip('/\\') if norm_path.startswith(norm_root) else path.lstrip('/\\')
    rel = rel.replace('\\', '/')
    _safe = "/:@!$&'()*+,;="
    return f'/photo/{quote(rel, safe=_safe)}'


def _spotify_id(track_id: str) -> str:
    return (track_id or '').replace('spotify:track:', '')


def _embed_url(track_id: str) -> str:
    tid = _spotify_id(track_id)
    return f'https://open.spotify.com/embed/track/{tid}?utm_source=generator&theme=0' if tid else ''


def _fmt_date(ts) -> str:
    if ts is None:
        return ''
    try:
        if pd.isna(ts):
            return ''
    except Exception:
        pass
    try:
        return pd.Timestamp(ts).strftime('%d %b %Y')
    except Exception:
        return ''


# ─── COMPOSANTS ───────────────────────────────────────────────────────────────

def _empty_state() -> html.Div:
    return html.Div(className='page-wrapper', children=[
        html.Div(className='page-empty-state', children=[
            dmc.ThemeIcon(
                DashIconify(icon="tabler:photo-heart", width=40),
                size=80, radius="xl", variant="light", color="violet",
                mb="lg",
            ),
            dmc.Title('Memory Album', order=2, mb="sm"),
            dmc.Text(
                "Lance d'abord les notebooks 03_memory_album/ dans l'ordre.",
                c="dimmed", mb="md",
            ),
            dmc.List(
                spacing="xs",
                children=[
                    dmc.ListItem('01_visual_embeddings.ipynb'),
                    dmc.ListItem('02_scene_clustering.ipynb'),
                    dmc.ListItem('03_music_matching.ipynb'),
                ],
                style={'color': ACCENT, 'textAlign': 'left', 'maxWidth': '320px', 'margin': '0 auto'},
            ),
        ])
    ])


def _photo_grid(photos: list) -> html.Div:
    if not photos:
        return html.Div('Aucune photo disponible', style={
            'color': 'rgba(255,255,255,0.2)', 'fontSize': '13px',
            'padding': '12px 0',
        })

    tiles = []
    for p in photos:
        url   = _photo_url(p['path'])
        music = p.get('music')
        # Badge ♫ si la photo a une musique propre
        badge = html.Div('♫', style={
            'position': 'absolute', 'bottom': '5px', 'right': '6px',
            'fontSize': '10px', 'color': SPOTIFY_GREEN,
            'background': 'rgba(0,0,0,0.65)', 'borderRadius': '4px',
            'padding': '1px 5px', 'lineHeight': '1.5',
            'pointerEvents': 'none',
        }) if (music and music.get('track_id')) else html.Span()

        tiles.append(html.Div(
            style={
                'position': 'relative', 'overflow': 'hidden',
                'borderRadius': '5px', 'background': '#1a1a22',
                'aspectRatio': '1',            # carré par défaut
            },
            children=[
                html.Img(
                    src=url,
                    style={
                        'width': '100%', 'height': '100%',
                        'objectFit': 'cover', 'display': 'block',
                    },
                ),
                badge,
            ]
        ))

    return html.Div(
        tiles,
        style={
            'display': 'grid',
            'gridTemplateColumns': 'repeat(auto-fill, minmax(150px, 1fr))',
            'gap': '4px',
            'marginTop': '14px',
        }
    )


def _music_card(scene: dict) -> html.Div:
    """Carte musique du groupe — absente si pas de match réel."""
    if not scene.get('track_id'):
        return html.Div()

    embed = _embed_url(scene['track_id'])
    cover = scene['cover_url']

    return html.Div(
        style={
            'marginTop': '18px',
            'borderRadius': '10px',
            'border': '1px solid rgba(29,185,84,0.25)',
            'background': 'rgba(29,185,84,0.07)',
            'overflow': 'hidden',
        },
        children=[
            html.Div(
                style={
                    'display': 'flex', 'alignItems': 'center',
                    'gap': '12px', 'padding': '12px 14px',
                },
                children=[
                    html.Img(src=cover, style={
                        'width': '44px', 'height': '44px',
                        'borderRadius': '6px', 'objectFit': 'cover', 'flexShrink': '0',
                    }) if cover else html.Div(style={
                        'width': '44px', 'height': '44px',
                        'background': '#1c1c24', 'borderRadius': '6px', 'flexShrink': '0',
                    }),
                    html.Div([
                        html.Div(scene['track_name'], style={
                            'fontSize': '14px', 'fontWeight': '600', 'color': '#fff',
                            'whiteSpace': 'nowrap', 'overflow': 'hidden',
                            'textOverflow': 'ellipsis', 'maxWidth': '500px',
                        }),
                        html.Div(scene['artist_name'], style={
                            'fontSize': '12px', 'color': SPOTIFY_GREEN, 'marginTop': '2px',
                        }),
                    ], style={'minWidth': '0', 'flex': '1'}),
                ]
            ),
            html.Iframe(
                src=embed,
                style={'width': '100%', 'height': '80px', 'border': 'none', 'display': 'block'},
                **{
                    'allow': 'autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture',
                },
            ) if embed else html.Div(),
        ]
    )


def _playlist_section(scene: dict) -> html.Div:
    pl = scene.get('playlist', [])
    if not pl:
        return html.Div()

    rows_el = []
    for i, t in enumerate(pl):
        cover  = t.get('album_cover_url', '')
        tid    = t.get('track_id', '')
        sp_url = f"https://open.spotify.com/track/{_spotify_id(tid)}" if tid else '#'
        rows_el.append(html.Div(
            style={
                'display': 'flex', 'alignItems': 'center', 'gap': '10px',
                'padding': '7px 14px',
                'borderTop': '1px solid rgba(255,255,255,0.05)',
            },
            children=[
                html.Span(str(i + 1), style={
                    'fontSize': '11px', 'color': 'rgba(255,255,255,0.3)',
                    'width': '18px', 'textAlign': 'right', 'flexShrink': '0',
                }),
                html.Img(src=cover, style={
                    'width': '34px', 'height': '34px', 'borderRadius': '4px',
                    'objectFit': 'cover', 'flexShrink': '0',
                }) if cover else html.Div(style={
                    'width': '34px', 'height': '34px',
                    'background': '#1c1c24', 'borderRadius': '4px', 'flexShrink': '0',
                }),
                html.Div([
                    html.Div(t.get('track_name', ''), style={
                        'fontSize': '13px', 'fontWeight': '500', 'color': '#fff',
                        'whiteSpace': 'nowrap', 'overflow': 'hidden',
                        'textOverflow': 'ellipsis',
                    }),
                    html.Div(t.get('artist_name', ''), style={
                        'fontSize': '11px', 'color': 'rgba(255,255,255,0.4)',
                        'marginTop': '1px',
                    }),
                ], style={'minWidth': '0', 'flex': '1'}),
                html.A('▶', href=sp_url, target='_blank', style={
                    'fontSize': '13px', 'color': SPOTIFY_GREEN,
                    'textDecoration': 'none', 'flexShrink': '0',
                }) if tid else html.Span(),
            ]
        ))

    return html.Div(style={'marginTop': '14px'}, children=[
        html.Details(children=[
            html.Summary(
                f"🎧 Playlist souvenir · {len(pl)} titres",
                style={
                    'fontSize': '12px', 'color': 'rgba(255,255,255,0.4)',
                    'cursor': 'pointer', 'padding': '6px 2px',
                    'listStyle': 'none', 'userSelect': 'none',
                }
            ),
            html.Div(rows_el, style={
                'marginTop': '6px', 'background': 'rgba(0,0,0,0.25)',
                'borderRadius': '8px', 'overflow': 'hidden',
            }),
        ])
    ])


_ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
          'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX',
          'XXI', 'XXII', 'XXIII', 'XXIV', 'XXV', 'XXVI', 'XXVII', 'XXVIII', 'XXIX', 'XXX']


def _scene_section(scene: dict, index: int) -> html.Div:
    num = _ROMAN[index % len(_ROMAN)]
    t0, t1 = _fmt_date(scene.get('ts_start')), _fmt_date(scene.get('ts_end'))
    date_label = f'{t0} — {t1}' if (t0 and t1 and t0 != t1) else (t0 or '')
    n_photos   = len(scene['photos'])

    return html.Div(
        style={
            'paddingTop': '44px',
            'paddingBottom': '44px',
            'borderBottom': '1px solid rgba(255,255,255,0.06)',
        },
        children=[
            # ── Titre de la scène ─────────────────────────────────────────────
            html.Div(
                style={'display': 'flex', 'alignItems': 'baseline', 'gap': '14px'},
                children=[
                    html.Span(num, style={
                        'fontSize': '30px', 'fontWeight': '800', 'color': ACCENT,
                        'fontFamily': 'Georgia, serif', 'lineHeight': '1',
                        'flexShrink': '0',
                    }),
                    html.H2(scene['scene_name'], style={
                        'fontSize': '20px', 'fontWeight': '700', 'color': '#fff',
                        'margin': '0', 'lineHeight': '1.3',
                    }),
                ]
            ),
            # ── Date + compteur ───────────────────────────────────────────────
            html.Div(
                style={'display': 'flex', 'gap': '16px', 'marginTop': '4px',
                       'alignItems': 'center'},
                children=[
                    html.Span(date_label, style={
                        'fontSize': '13px', 'color': 'rgba(255,255,255,0.38)',
                    }) if date_label else html.Span(),
                    html.Span(
                        f"{n_photos} photo{'s' if n_photos != 1 else ''}",
                        style={'fontSize': '12px', 'color': 'rgba(255,255,255,0.22)'},
                    ),
                ]
            ),
            # ── Grille photos ─────────────────────────────────────────────────
            _photo_grid(scene['photos']),
            # ── Musique du moment ─────────────────────────────────────────────
            _music_card(scene),
            # ── Playlist souvenir ─────────────────────────────────────────────
            _playlist_section(scene),
        ]
    )


# ─── LAYOUT ───────────────────────────────────────────────────────────────────

def layout() -> html.Div:
    album = _load_album()
    if not album:
        return _empty_state()

    scenes      = list(album.values())
    n_photos    = sum(len(s['photos']) for s in scenes)
    n_musical   = sum(1 for s in scenes if s.get('track_id'))

    dates = []
    for s in scenes:
        ts = s.get('ts_start')
        if ts is not None:
            try:
                t = pd.Timestamp(ts)
                if not pd.isna(t):
                    dates.append(t)
            except Exception:
                pass
    if dates:
        d0 = min(dates).strftime('%b %Y')
        d1 = max(dates).strftime('%b %Y')
        date_range = f'{d0} — {d1}' if d0 != d1 else d0
    else:
        date_range = ''

    return html.Div(
        className='page-wrapper',
        style={'maxWidth': '860px', 'margin': '0 auto', 'padding': '48px 32px 80px'},
        children=[
            # ── En-tête global ────────────────────────────────────────────────
            html.Div(style={'marginBottom': '52px'}, children=[
                dmc.Text(
                    'MEMORY ALBUM',
                    size='xs', fw=700, c='violet',
                    style={'letterSpacing': '0.2em', 'marginBottom': '8px'},
                ),
                dmc.Title(
                    'Mes scènes de vie', order=1,
                    style={'fontFamily': 'Georgia, serif', 'marginBottom': '6px'},
                ),
                dmc.Text(date_range, c='dimmed', size='md', mb='xl') if date_range else html.Span(),
                dmc.Group(
                    gap='xl',
                    children=[
                        _stat_block(str(len(scenes)), 'moments'),
                        _stat_block(str(n_photos),    'photos'),
                        _stat_block(str(n_musical),   'avec musique'),
                    ]
                ),
            ]),
            # ── Sections ──────────────────────────────────────────────────────
            html.Div([_scene_section(s, i) for i, s in enumerate(scenes)]),
        ]
    )


def _stat_block(value: str, label: str) -> html.Div:
    return dmc.Stack(
        gap=2,
        children=[
            dmc.Text(value, size='xl', fw=800, lh=1),
            dmc.Text(label, size='xs', c='dimmed', style={'letterSpacing': '0.05em'}),
        ]
    )
