"""
parsers/instagram.py — Déplacement export GDPR Instagram
=========================================================

inbox/instagram-*/  →  processed/INSTAGRAM/

Structure cible (attendue par src/scripts/01_exploration/instagram.ipynb) :
    processed/INSTAGRAM/
    ├── your_instagram_activity/
    │   ├── likes/liked_posts.json
    │   ├── messages/inbox/*/message_*.json
    │   └── ...
    ├── connections/followers_and_following/
    ├── ads_information/
    └── ...

Plusieurs exports sont fusionnés (OVERWRITE=False → le plus ancien gagne pour
les fichiers en conflit, ce qui préserve l'historique maximal).
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.ingestion.base import ParserBase, move_files


class InstagramParser(ParserBase):

    SOURCE_NAME          = "INSTAGRAM"
    OVERWRITE            = False
    EXPECTED_EXTENSIONS  = {".json"}

    def move(self) -> int:
        folders = self._inbox_folders()
        os.makedirs(self.dest, exist_ok=True)
        total = 0
        for folder in folders:
            moved = move_files(folder, self.dest, overwrite=self.OVERWRITE)
            total += moved
            self._logger.debug(f"[INSTAGRAM] {os.path.basename(folder)} → {moved} fichier(s) déplacé(s)")
        return total


if __name__ == "__main__":
    InstagramParser().run()
