"""
parsers/google.py — Déplacement export Google Takeout
======================================================

inbox/takeout-*/  →  processed/GOOGLE/

Structure cible (attendue par src/scripts/01_exploration/google_youtube.ipynb) :
    processed/GOOGLE/
    ├── Mon activité/
    │   ├── Recherche/MonActivité.html
    │   └── Chrome/MonActivité.html
    └── YouTube et YouTube Music/
        └── historique/
            ├── watch-history.html
            └── Historique des recherches.html

Format Takeout : takeout-xxx/ ou takeout-xxx/Takeout/ comme racine.
Plusieurs archives fusionnées (OVERWRITE=False).
"""

import os
import sys
import shutil
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.ingestion.base import ParserBase


class GoogleParser(ParserBase):

    SOURCE_NAME          = "GOOGLE"
    OVERWRITE            = False
    EXPECTED_EXTENSIONS  = {".html", ".json"}

    def move(self) -> int:
        folders = self._inbox_folders()
        os.makedirs(self.dest, exist_ok=True)
        total = 0
        for folder in sorted(folders):
            moved = self._move_archive(folder)
            total += moved
            self._logger.debug(f"[GOOGLE] {os.path.basename(folder)} → {moved} fichier(s) déplacé(s)")
        return total

    def _move_archive(self, archive_dir: str) -> int:
        takeout_sub = os.path.join(archive_dir, "Takeout")
        root = takeout_sub if os.path.isdir(takeout_sub) else archive_dir

        moved = 0
        for src_path in Path(root).rglob("*"):
            if not src_path.is_file():
                continue
            dst_path = Path(self.dest) / src_path.relative_to(root)
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if dst_path.exists() and not self.OVERWRITE:
                continue
            shutil.move(str(src_path), str(dst_path))
            moved += 1
        return moved


if __name__ == "__main__":
    GoogleParser().run()
