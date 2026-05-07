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

from src.ingestion.base import ParserBase, INBOX_ROOT, IngestionValidationError


class NetflixParser(ParserBase):

    SOURCE_NAME          = "NETFLIX"
    OVERWRITE            = True
    EXPECTED_EXTENSIONS  = {".csv"}

    FILENAME = "NetflixViewingHistory.csv"

    def validate(self, folders: list[str]) -> list[str]:
        src = os.path.join(self.inbox, self.FILENAME)
        if not os.path.isfile(src):
            return []  # Pas de fichier = skip, géré dans run()
        size = os.path.getsize(src)
        if size == 0:
            raise IngestionValidationError(f"{self.FILENAME} présent mais vide (0 octet)")
        return []

    def move(self) -> int:
        src = os.path.join(self.inbox, self.FILENAME)
        if not os.path.isfile(src):
            return 0
        os.makedirs(self.dest, exist_ok=True)
        dst = os.path.join(self.dest, self.FILENAME)
        shutil.move(src, dst)
        self._logger.debug(f"[NETFLIX] {self.FILENAME} → processed/NETFLIX/")
        return 1

    def run(self) -> int:
        """Override : Netflix utilise un fichier direct, pas un sous-dossier inbox."""
        self._skipped = False
        log = self._logger
        log.info(f"[{self.SOURCE_NAME}] Déplacement inbox → processed/")

        src = os.path.join(self.inbox, self.FILENAME)
        if not os.path.isfile(src):
            log.info(f"[{self.SOURCE_NAME}] Aucun fichier {self.FILENAME} dans inbox/ — skip")
            self._skipped = True
            return 0

        try:
            self.validate([])
        except IngestionValidationError as e:
            log.error(f"[{self.SOURCE_NAME}] Validation échouée — {e}")
            raise

        total = self.move()
        log.info(f"[{self.SOURCE_NAME}] {total} fichier(s) déplacé(s) vers processed/{self.SOURCE_NAME}/")
        return total


if __name__ == "__main__":
    NetflixParser().run()
