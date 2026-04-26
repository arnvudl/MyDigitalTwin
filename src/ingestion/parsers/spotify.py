"""
parsers/spotify.py — Déplacement export Spotify GDPR
=====================================================

inbox/Spotify Account Data/          →  processed/SPOTIFY/account/
inbox/Spotify Extended Streaming History/  →  processed/SPOTIFY/extended/

Structure cible :
    processed/SPOTIFY/
    ├── account/
    │   ├── StreamingHistory_music_0.json  ... (streams récents, ~1 an)
    │   ├── YourLibrary.json               (tracks/albums/artists likés)
    │   ├── SearchQueries.json
    │   └── ...
    └── extended/
        ├── Streaming_History_Audio_2020-2022_0.json  (historique complet depuis 2020)
        └── ...

OVERWRITE=False : les exports sont cumulatifs, on préserve l'existant.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.ingestion.base import ParserBase, move_files


class SpotifyParser(ParserBase):

    SOURCE_NAME = "SPOTIFY"
    OVERWRITE   = False

    # Mapping : fragment du nom de dossier inbox → sous-dossier dans processed/SPOTIFY/
    _FOLDER_MAP = {
        "account data":           "account",
        "extended streaming":     "extended",
    }

    def move(self) -> int:
        folders = self._inbox_folders()
        os.makedirs(self.dest, exist_ok=True)
        total = 0
        for folder in sorted(folders):
            name_lower = os.path.basename(folder).lower()
            # Détecter le sous-dossier cible
            sub = next(
                (dst for key, dst in self._FOLDER_MAP.items() if key in name_lower),
                "account"   # fallback
            )
            dst = os.path.join(self.dest, sub)
            moved = move_files(folder, dst, overwrite=self.OVERWRITE)
            total += moved
            print(f"[SPOTIFY] {os.path.basename(folder)} → {sub}/ ({moved} fichiers)")
        return total


if __name__ == "__main__":
    SpotifyParser().run()
