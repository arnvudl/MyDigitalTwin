"""
parsers/twitter.py — Déplacement export Twitter/X
==================================================

inbox/twitter-*/  →  processed/X/

Structure cible (attendue par src/scripts/01_exploration/twitter.ipynb) :
    processed/X/
    ├── data/
    │   ├── tweets.js
    │   ├── like.js
    │   ├── follower.js
    │   ├── following.js
    │   └── ... (94 fichiers .js)
    └── Your archive.html

Export monolithique : OVERWRITE=True (le plus récent remplace toujours).
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.ingestion.base import ParserBase, move_files


class TwitterParser(ParserBase):

    SOURCE_NAME = "X"
    OVERWRITE   = True

    def move(self) -> int:
        folders = self._inbox_folders()
        os.makedirs(self.dest, exist_ok=True)
        total = 0
        for folder in sorted(folders):
            moved = move_files(folder, self.dest, overwrite=self.OVERWRITE)
            total += moved
            print(f"[X] {os.path.basename(folder)} → {moved} fichiers déplacés")
        return total


if __name__ == "__main__":
    TwitterParser().run()
