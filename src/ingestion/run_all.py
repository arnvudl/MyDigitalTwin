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
    "instagram": {
      "last_run":   "2026-04-26T15:30:00",
      "status":     "ok|skip|error",
      "files_moved": 3,
      "duration_s":  0.8,
      "error":       null
    }
  }
}

Si au moins une source est en erreur, data/alerts.json est écrit.

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

from src.ingestion.logger import get_logger
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

_PROJECT_ROOT  = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LOG_PATH      = os.path.join(_PROJECT_ROOT, "data", "ingestion_log.json")
_ALERTS_PATH   = os.path.join(_PROJECT_ROOT, "data", "alerts.json")


def _load_log() -> dict:
    if os.path.isfile(_LOG_PATH):
        try:
            with open(_LOG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_run": None, "sources": {}}


def _save_log(log: dict) -> None:
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    with open(_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def _save_alerts(errors: dict, now_iso: str) -> None:
    existing = []
    if os.path.isfile(_ALERTS_PATH):
        try:
            with open(_ALERTS_PATH, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.append({"timestamp": now_iso, "errors": errors})
    with open(_ALERTS_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="MyDigitalTwin — Ingestion GDPR (inbox → processed)")
    parser.add_argument(
        "--sources", nargs="+", choices=list(ALL_PARSERS.keys()),
        default=list(ALL_PARSERS.keys()),
        help="Sources à traiter (défaut : toutes)"
    )
    args = parser.parse_args()

    log     = get_logger("ingestion.run_all")
    t_start = time.time()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    audit   = _load_log()
    results: dict[str, dict] = {}

    log.info("=" * 60)
    log.info("MyDigitalTwin — Ingestion GDPR (inbox → processed/)")
    log.info(f"Sources : {', '.join(args.sources)}")
    log.info("=" * 60)

    for name in args.sources:
        t0 = time.time()
        try:
            p     = ALL_PARSERS[name]()
            total = p.run()
            status = "skip" if getattr(p, "_skipped", False) else "ok"
            results[name] = {
                "status":     status,
                "files_moved": total,
                "duration_s": round(time.time() - t0, 2),
                "error":      None,
            }
        except Exception as exc:
            log.error(f"[{name.upper()}] Erreur non gérée : {exc}", exc_info=True)
            results[name] = {
                "status":     "error",
                "files_moved": 0,
                "duration_s": round(time.time() - t0, 2),
                "error":      str(exc),
            }

        audit.setdefault("sources", {})[name] = {
            "last_run": now_iso,
            **results[name],
        }

    audit["last_run"] = now_iso
    _save_log(audit)

    errors = {k: v for k, v in results.items() if v["status"] == "error"}
    if errors:
        _save_alerts(errors, now_iso)
        log.error(f"ALERTE : {len(errors)} source(s) en erreur → {_ALERTS_PATH}")

    elapsed = time.time() - t_start
    log.info("=" * 60)
    log.info(f"Terminé en {elapsed:.0f}s")
    for name, r in results.items():
        icon = {"ok": "OK  ", "skip": "SKIP", "error": "FAIL"}[r["status"]]
        line = f"  [{icon}] {name.upper():<12} {r['files_moved']:>4} fichier(s)  ({r['duration_s']}s)"
        if r["status"] == "error":
            log.error(line + f"  — {r['error']}")
        else:
            log.info(line)
    log.info(f"Audit log → {_LOG_PATH}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
