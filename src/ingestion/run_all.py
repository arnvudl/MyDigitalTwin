"""
run_all.py — Lance tous les parsers disponibles en séquence
============================================================

Chaque parser déplace les exports GDPR depuis data/inbox/ vers data/processed/.
Aucune Spark session n'est créée ici ; le warehouse est géré par src/scripts/.

Après chaque exécution, un audit log est mis à jour dans :
    data/ingestion_log.json

Format :
{
  "last_run": "2026-04-26T15:30:00",
  "sources": {
    "instagram": {"last_run": "2026-04-26T15:30:00", "files_moved": 3},
    ...
  }
}

Usage :
    python -m src.ingestion.run_all
    python -m src.ingestion.run_all --sources instagram google
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingestion.parsers.instagram import InstagramParser
from src.ingestion.parsers.google    import GoogleParser
from src.ingestion.parsers.tiktok    import TikTokParser
from src.ingestion.parsers.twitter   import TwitterParser
from src.ingestion.parsers.spotify   import SpotifyParser
from src.ingestion.parsers.netflix   import NetflixParser


ALL_PARSERS = {
    "instagram": InstagramParser,
    "google":    GoogleParser,
    "tiktok":    TikTokParser,
    "twitter":   TwitterParser,
    "spotify":   SpotifyParser,
    "netflix":   NetflixParser,
}

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LOG_PATH     = os.path.join(_PROJECT_ROOT, "data", "ingestion_log.json")


def _load_log() -> dict:
    """Charge le log existant ou retourne un dict vide."""
    if os.path.isfile(_LOG_PATH):
        try:
            with open(_LOG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_run": None, "sources": {}}


def _save_log(log: dict) -> None:
    """Persiste le log sur disque (crée data/ si nécessaire)."""
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    with open(_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="MyDigitalTwin — Ingestion GDPR (inbox → processed)")
    parser.add_argument(
        "--sources", nargs="+", choices=list(ALL_PARSERS.keys()),
        default=list(ALL_PARSERS.keys()),
        help="Sources à déplacer (défaut : toutes)"
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  MyDigitalTwin - Deplacement inbox -> processed/")
    print("="*60)
    print(f"  Sources : {', '.join(args.sources)}")
    print("="*60)

    t_start  = time.time()
    now_iso  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    summary  = {}
    log      = _load_log()

    for name in args.sources:
        p     = ALL_PARSERS[name]()
        total = p.run()
        summary[name] = total

        # Mise à jour de l'entrée source dans le log
        log.setdefault("sources", {})[name] = {
            "last_run":    now_iso,
            "files_moved": total,
        }

    log["last_run"] = now_iso
    _save_log(log)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  Déplacement terminé en {elapsed:.0f}s")
    print("="*60)
    for source, total in summary.items():
        print(f"  {source.upper():<12} {total:>6} fichiers déplacés")
    print(f"\n  Audit log → {_LOG_PATH}")
    print()


if __name__ == "__main__":
    main()
