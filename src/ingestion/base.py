"""
base.py — Classe de base pour les parsers d'ingestion
======================================================

Rôle des parsers : déplacer les exports GDPR depuis inbox/ vers processed/
en normalisant l'arborescence pour que les scripts (src/scripts/) trouvent
les fichiers aux chemins attendus.

Flux :
    data/inbox/  →  (parser.move())  →  data/processed/<SOURCE>/

Les scripts src/scripts/ lisent depuis processed/ et écrivent le warehouse.

Détection de la source par regex sur le nom du dossier inbox :
    instagram*  → INSTAGRAM
    takeout*    → GOOGLE
    tiktok*     → TIKTOK
    twitter*    → X
"""

import os
import re
import shutil
from pathlib import Path

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config import INBOX_ROOT, PROCESSED_DATA
from src.ingestion.logger import get_logger

INBOX_PATTERNS = [
    (re.compile(r"^instagram",         re.IGNORECASE), "INSTAGRAM"),
    (re.compile(r"^takeout",           re.IGNORECASE), "GOOGLE"),
    (re.compile(r"^tiktok",            re.IGNORECASE), "TIKTOK"),
    (re.compile(r"^twitter",           re.IGNORECASE), "X"),
    (re.compile(r"^spotify",           re.IGNORECASE), "SPOTIFY"),
]


class IngestionValidationError(Exception):
    """Erreur levée quand la structure du dossier inbox est invalide."""
    pass


def detect_source(folder_name: str) -> str | None:
    for pattern, source in INBOX_PATTERNS:
        if pattern.match(folder_name):
            return source
    return None


def scan_inbox(inbox_root: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    if not os.path.isdir(inbox_root):
        return grouped
    for entry in sorted(os.listdir(inbox_root)):
        full = os.path.join(inbox_root, entry)
        if not os.path.isdir(full):
            continue
        source = detect_source(entry)
        if source:
            grouped.setdefault(source, []).append(full)
    return grouped


def move_files(src_dir: str, dst_dir: str, overwrite: bool = False) -> int:
    moved = 0
    for src_path in Path(src_dir).rglob("*"):
        if not src_path.is_file():
            continue
        rel      = src_path.relative_to(src_dir)
        dst_path = Path(dst_dir) / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists() and not overwrite:
            continue
        shutil.move(str(src_path), str(dst_path))
        moved += 1
    return moved


class ParserBase:
    SOURCE_NAME:         str      = ""
    OVERWRITE:           bool     = False
    EXPECTED_EXTENSIONS: set[str] = {".json"}

    def __init__(self):
        self.inbox          = INBOX_ROOT
        self.processed_root = PROCESSED_DATA
        self.dest           = os.path.join(PROCESSED_DATA, self.SOURCE_NAME)
        self._skipped       = False
        self._logger        = get_logger(f"ingestion.{self.SOURCE_NAME.lower()}")

    def _inbox_folders(self) -> list[str]:
        return scan_inbox(self.inbox).get(self.SOURCE_NAME, [])

    def validate(self, folders: list[str]) -> list[str]:
        """
        Vérifie la structure des dossiers inbox avant le déplacement.
        Retourne une liste de warnings (chaînes). Liste vide = OK.
        Lève IngestionValidationError si le dossier est présent mais vide.
        """
        warnings = []
        for folder in folders:
            actual_files = [f for f in Path(folder).rglob("*") if Path(f).is_file()]
            if not actual_files:
                raise IngestionValidationError(f"Dossier inbox vide : {folder}")
            exts = {Path(f).suffix.lower() for f in actual_files}
            if not (exts & self.EXPECTED_EXTENSIONS):
                warnings.append(
                    f"{os.path.basename(folder)} : aucun fichier {self.EXPECTED_EXTENSIONS} "
                    f"(extensions trouvées : {exts})"
                )
        return warnings

    def move(self) -> int:
        raise NotImplementedError

    def run(self) -> int:
        self._skipped = False
        log = self._logger
        log.info(f"[{self.SOURCE_NAME}] Déplacement inbox → processed/")

        folders = self._inbox_folders()
        if not folders:
            log.info(f"[{self.SOURCE_NAME}] Aucun dossier inbox détecté — skip")
            self._skipped = True
            return 0

        log.debug(f"[{self.SOURCE_NAME}] {len(folders)} dossier(s) trouvé(s) : "
                  f"{[os.path.basename(f) for f in folders]}")

        try:
            warnings = self.validate(folders)
        except IngestionValidationError as e:
            log.error(f"[{self.SOURCE_NAME}] Validation échouée — {e}")
            raise

        for w in warnings:
            log.warning(f"[{self.SOURCE_NAME}] Validation : {w}")

        total = self.move()
        log.info(f"[{self.SOURCE_NAME}] {total} fichier(s) déplacé(s) vers processed/{self.SOURCE_NAME}/")
        return total
