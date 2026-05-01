"""
apply_moment_tags.py — Applique les moment tags LLM dans music_library.json

Par défaut lit : data/LLM_DATA/response_llm.json
Usage optionnel : python apply_moment_tags.py <chemin_vers_reponse_json>

La réponse JSON doit avoir la forme renvoyée par le LLM :
    {
      "spotify:track:ID1": ["tag1", "tag2", "tag3"],
      "spotify:track:ID2": ["tag1", "tag2"],
      ...
    }
"""

import sys
import os
import json

# ── Localiser config.py ──────────────────────────────────────────────────────
_root = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_root, 'config.py')):
    _parent = os.path.dirname(_root)
    if _parent == _root:
        raise RuntimeError("config.py introuvable")
    _root = _parent

sys.path.insert(0, _root)
from config import MUSIC_LIBRARY_PATH, LLM_DATA

# ── Chemin de la réponse LLM (arg CLI ou défaut) ──────────────────────────────
DEFAULT_RESPONSE = os.path.join(LLM_DATA, 'response_llm.json')
response_path = sys.argv[1] if len(sys.argv) >= 2 else DEFAULT_RESPONSE

if not os.path.exists(response_path):
    print(f"❌ Fichier introuvable : {response_path}")
    if response_path == DEFAULT_RESPONSE:
        print(f"   Dépose la réponse du LLM dans : {DEFAULT_RESPONSE}")
    sys.exit(1)

print(f"Lecture réponse LLM : {response_path}")

# ── Lecture réponse LLM ──────────────────────────────────────────────────────
with open(response_path, encoding='utf-8') as _f:
    raw = _f.read().strip()

# Tolérance : si le LLM a entouré le JSON de ```json ... ```
if raw.startswith('```'):
    lines = raw.splitlines()
    raw = '\n'.join(l for l in lines if not l.startswith('```'))

try:
    tags_map: dict = json.loads(raw)   # {track_id: [tags]}
except json.JSONDecodeError as e:
    print(f"❌ Réponse JSON invalide : {e}")
    sys.exit(1)

# ── Merge dans music_library.json ────────────────────────────────────────────
if not os.path.exists(MUSIC_LIBRARY_PATH):
    print(f"❌ music_library.json introuvable : {MUSIC_LIBRARY_PATH}")
    print("   Lance d'abord : python src/scripts/03_memory_album/build_music_library.py")
    sys.exit(1)

with open(MUSIC_LIBRARY_PATH, encoding='utf-8') as _f:
    library = json.load(_f)

updated = 0
for entry in library:
    tid  = entry['track_id']
    tags = tags_map.get(tid)
    if tags and isinstance(tags, list):
        entry['moments'] = [str(t) for t in tags]
        updated += 1

with open(MUSIC_LIBRARY_PATH, 'w', encoding='utf-8') as _f:
    json.dump(library, _f, ensure_ascii=False, indent=2)

total_with_tags = sum(1 for e in library if e.get('moments'))
print(f"✓ {updated} titres mis à jour → {MUSIC_LIBRARY_PATH}")
print(f"  {total_with_tags}/{len(library)} titres ont maintenant des moment tags")

remaining = len(library) - total_with_tags
if remaining > 0:
    print(f"  {remaining} titres restent sans tags (relance build_music_library.py pour un nouveau prompt)")
