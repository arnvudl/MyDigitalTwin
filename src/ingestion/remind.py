"""
remind.py — Rappels GDPR pour les exports de données personnelles.

Usage :
    python src/ingestion/remind.py           # Affiche l'état de chaque plateforme
    python src/ingestion/remind.py --update  # Marque un export comme fait
"""
import json
import sys
import os
from datetime import date, datetime
from pathlib import Path

# Fix Windows console UTF-8
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8")

LOG_PATH = Path(__file__).parent / "ingestion_log.json"
REFRESH_DAYS = 90  # Rappel tous les 90 jours


def _load() -> dict:
    with open(LOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _days_since(date_str: str | None) -> int | None:
    if not date_str:
        return None
    d = datetime.fromisoformat(date_str).date()
    return (date.today() - d).days


def show_status() -> None:
    data = _load()
    print(f"\n{'─' * 60}")
    print(f"  GDPR Export Status — {date.today()}")
    print(f"{'─' * 60}")

    needs_action = []
    for platform, cfg in data["platforms"].items():
        days = _days_since(cfg["last_export_date"])
        if days is None:
            status = "⚠️  JAMAIS exporté"
            needs_action.append(platform)
        elif days > REFRESH_DAYS:
            status = f"⚠️  Il y a {days}j (> {REFRESH_DAYS}j)"
            needs_action.append(platform)
        else:
            status = f"✅  Il y a {days}j"

        last_ingest = cfg.get("last_ingested") or "—"
        print(f"\n  {platform.upper():<12} {status}")
        print(f"  {'':12} Dernier ingestion : {last_ingest}")
        print(f"  {'':12} {cfg['notes']}")

    print(f"\n{'─' * 60}")
    if needs_action:
        print(f"  Action requise pour : {', '.join(needs_action)}")
    else:
        print("  Tout est à jour.")
    print(f"{'─' * 60}\n")


def mark_exported(platform: str) -> None:
    data = _load()
    if platform not in data["platforms"]:
        print(f"Plateforme inconnue : {platform}")
        print(f"Disponibles : {', '.join(data['platforms'].keys())}")
        sys.exit(1)
    today = date.today().isoformat()
    data["platforms"][platform]["last_export_date"] = today
    _save(data)
    print(f"✅  {platform} marqué exporté le {today}")


def mark_ingested(platform: str) -> None:
    data = _load()
    if platform not in data["platforms"]:
        print(f"Plateforme inconnue : {platform}")
        sys.exit(1)
    today = date.today().isoformat()
    data["platforms"][platform]["last_ingested"] = today
    _save(data)
    print(f"✅  {platform} marqué ingéré le {today}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        show_status()
    elif args[0] == "--exported" and len(args) == 2:
        mark_exported(args[1])
    elif args[0] == "--ingested" and len(args) == 2:
        mark_ingested(args[1])
    else:
        print(__doc__)
