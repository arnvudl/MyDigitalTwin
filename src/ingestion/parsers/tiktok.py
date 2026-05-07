"""
parsers/tiktok.py — Déplacement export GDPR TikTok
===================================================

inbox/TikTok_Data_*/  →  processed/TIKTOK/

Structure cible (attendue par src/scripts/01_exploration/tiktok.ipynb) :
    processed/TIKTOK/
    └── user_data_tiktok.json

Export monolithique : OVERWRITE=True (le plus récent remplace toujours).
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.ingestion.base import ParserBase, move_files


class TikTokParser(ParserBase):

    SOURCE_NAME          = "TIKTOK"
    OVERWRITE            = True
    EXPECTED_EXTENSIONS  = {".json"}

    def move(self) -> int:
        folders = self._inbox_folders()
        os.makedirs(self.dest, exist_ok=True)
        total = 0
        for folder in sorted(folders):
            moved = move_files(folder, self.dest, overwrite=self.OVERWRITE)
            total += moved
            self._logger.debug(f"[TIKTOK] {os.path.basename(folder)} → {moved} fichier(s) déplacé(s)")
        return total


if __name__ == "__main__":
    TikTokParser().run()
