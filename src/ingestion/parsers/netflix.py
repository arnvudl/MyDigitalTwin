"""
parsers/netflix.py — Déplacement export Netflix
================================================

inbox/NetflixViewingHistory.csv  →  processed/NETFLIX/NetflixViewingHistory.csv

Netflix exporte l'historique complet en un seul fichier CSV plat
(pas de sous-dossier contrairement aux autres sources GDPR).

OVERWRITE=True : chaque export remplace l'historique complet.
"""

import os
import shutil
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.ingestion.base import ParserBase, INBOX_ROOT


class NetflixParser(ParserBase):

    SOURCE_NAME = "NETFLIX"
    OVERWRITE   = True   # Export complet à chaque fois

    FILENAME = "NetflixViewingHistory.csv"

    def move(self) -> int:
        src = os.path.join(self.inbox, self.FILENAME)
        if not os.path.isfile(src):
            return 0
        os.makedirs(self.dest, exist_ok=True)
        dst = os.path.join(self.dest, self.FILENAME)
        shutil.move(src, dst)
        print(f"[NETFLIX] {self.FILENAME} -> processed/NETFLIX/ (1 fichier)")
        return 1

    def run(self) -> int:
        """Override : pas de sous-dossier inbox à détecter pour Netflix."""
        print(f"\n[NETFLIX] Déplacement inbox -> processed/")
        src = os.path.join(self.inbox, self.FILENAME)
        if not os.path.isfile(src):
            print(f"[NETFLIX] Aucun fichier {self.FILENAME} dans inbox/ — skip")
            return 0
        total = self.move()
        print(f"[NETFLIX] {total} fichier déplacé vers processed/NETFLIX/")
        return total


if __name__ == "__main__":
    NetflixParser().run()
