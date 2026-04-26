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
from config import PROJECT_ROOT, PROCESSED_DATA

INBOX_ROOT = os.path.join(PROJECT_ROOT, "data", "inbox")

INBOX_PATTERNS = [
    (re.compile(r"^instagram", re.IGNORECASE), "INSTAGRAM"),
    (re.compile(r"^takeout",   re.IGNORECASE), "GOOGLE"),
    (re.compile(r"^tiktok",    re.IGNORECASE), "TIKTOK"),
    (re.compile(r"^twitter",   re.IGNORECASE), "X"),
]


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
    SOURCE_NAME: str  = ""
    OVERWRITE:   bool = False

    def __init__(self):
        self.inbox          = INBOX_ROOT
        self.processed_root = PROCESSED_DATA
        self.dest           = os.path.join(PROCESSED_DATA, self.SOURCE_NAME)

    def _inbox_folders(self) -> list[str]:
        return scan_inbox(self.inbox).get(self.SOURCE_NAME, [])

    def move(self) -> int:
        raise NotImplementedError

    def run(self) -> int:
        print(f"\n[{self.SOURCE_NAME}] Déplacement inbox → processed/")
        folders = self._inbox_folders()
        if not folders:
            print(f"[{self.SOURCE_NAME}] Aucun dossier inbox détecté — skip")
            return 0
        total = self.move()
        print(f"[{self.SOURCE_NAME}] {total} fichiers déplacés vers processed/{self.SOURCE_NAME}/")
        return total
