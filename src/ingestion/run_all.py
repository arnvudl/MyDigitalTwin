"""
run_all.py — Lance tous les parsers disponibles en séquence
============================================================

Chaque parser déplace les exports GDPR depuis data/inbox/ vers data/processed/.
Aucune Spark session n'est créée ici ; le warehouse est géré par src/scripts/.

Usage :
    python -m src.ingestion.run_all
    python -m src.ingestion.run_all --sources instagram google
"""

import argparse
import os
import sys
import time

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

    t_start = time.time()
    summary = {}

    for name in args.sources:
        p = ALL_PARSERS[name]()
        total = p.run()
        summary[name] = total

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  Déplacement terminé en {elapsed:.0f}s")
    print("="*60)
    for source, total in summary.items():
        print(f"  {source.upper():<12} {total:>6} fichiers déplacés")
    print()


if __name__ == "__main__":
    main()
