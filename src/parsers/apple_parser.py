"""
MyDigitalTwin — Parser Apple
==============================
Parse les exports Apple (CSV + JSON) et produit des datasets propres.

Fichiers traités :
    AppInstallActivity/App Install Activity.csv     → app_installs.csv
    AppleAccountInformation/Apple ID Device Information.csv → devices.csv
    AppleAccountInformation/Apps Using Sign In with Apple.csv → signin_apps.csv
    Calendriers et rappels iCloud/Calendar Metadata.json → calendars.csv

Fichiers ignorés (confidentialité / inutilité analytique) :
    Apple Card User Information.csv     → données bancaires
    Apple Pay Cards.csv                 → données bancaires
    Apple Pay Cloud Tokens.csv          → tokens sécurité
    Apple ID Account Information.csv    → infos perso brutes
    Apple ID SignOn Information.csv     → logs de connexion
    Data & Privacy Request History.csv  → meta
    Hide My Email Information.csv       → aliases email
    Passkeys Information.csv            → sécurité
    Marketing Communications Delivery.csv → pub

Usage :
    python apple_parser.py --input ./data/raw/APPLE --output ./data/processed/apple
"""

import csv
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def fix_encoding(text: str) -> str:
    """Corrige le double encodage UTF-8 (Evanâ€™s → Evan's, cp1252 → utf-8)."""
    if not text:
        return text
    for enc in ("latin-1", "cp1252"):
        try:
            result = text.encode(enc).decode("utf-8")
            if result != text:
                return result
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


def clean(val: str) -> str:
    """Nettoie une valeur CSV."""
    if not val:
        return ""
    val = val.strip().strip('"')
    if val in ("N/A", "n/a", "None", "null", ""):
        return ""
    return fix_encoding(val)


def ts_to_iso(date_str: str) -> str:
    """Normalise une date en ISO 8601."""
    if not date_str:
        return ""
    date_str = date_str.strip().strip('"')
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%m-%d-%Y %H:%M:%S",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return date_str


def read_csv(path: Path) -> list:
    """Lit un CSV Apple avec gestion d'encodage."""
    for enc in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                return list(csv.DictReader(f))
        except Exception:
            continue
    return []


def write_csv(rows: list, path: Path) -> int:
    if not rows:
        print(f"  [~] Vide — {path.name}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [✓] {path.name:<45} {len(rows):>5} lignes")
    return len(rows)


# ══════════════════════════════════════════════════════════════════════════════
# PARSERS
# ══════════════════════════════════════════════════════════════════════════════

def parse_app_installs(path: Path) -> list:
    """
    App Install Activity.csv
    Colonnes gardées : app_name, app_id, event_type, event_date,
                       platform, ios_version, installation_type
    Colonnes supprimées : Apple ID Number, Device Identifier (identifiants perso),
                          Client Event ID, External Referral URL, OS Build Version,
                          Store Front Name, Origin
    """
    rows_raw = read_csv(path)
    if not rows_raw:
        return []

    rows = []
    for r in rows_raw:
        event_date = ts_to_iso(r.get("Event Date", ""))
        rows.append({
            "app_name":          fix_encoding(r.get("App Name", "")),
            "app_id":            clean(r.get("Application ID", "")),
            "app_type":          clean(r.get("Application Type", "")),
            "installation_type": clean(r.get("Installation Type", "")),
            "event_date":        event_date,
            "event_month":       event_date[:7] if event_date else "",
            "event_year":        event_date[:4] if event_date else "",
            "platform":          clean(r.get("Platform Name", "")),
            "ios_version":       clean(r.get("Device OS Version", "")),
            "source":            "apple",
            "type":              "app_install",
        })
    return rows


def parse_devices(path: Path) -> list:
    """
    Apple ID Device Information.csv
    Colonnes gardées : device_name, device_model, os_version, timezone, locale
    Colonnes supprimées : IMEI, Serial Number, IP, ICCID, MEID (données sensibles)
    """
    rows_raw = read_csv(path)
    if not rows_raw:
        return []

    rows = []
    for r in rows_raw:
        device_name = fix_encoding(r.get("Device Name", ""))
        # Anonymiser les noms de device qui contiennent des prénoms
        # On garde le modèle, pas le nom personnalisé
        model = clean(r.get("Device Model Name", ""))
        rows.append({
            "device_name":    device_name[:50],
            "device_model":   model,
            "os_version":     clean(r.get("Device OS Version", "")),
            "timezone":       clean(r.get("Device Time Zone", "")),
            "locale":         clean(r.get("Device Locale Language", "")),
            "added_date":     ts_to_iso(r.get("Device Added Date", "")),
            "source":         "apple",
            "type":           "device",
        })
    return rows


def parse_signin_apps(path: Path) -> list:
    """
    Apps Using Sign In with Apple.csv
    Quelles apps tu utilises avec ton Apple ID → centres d'intérêt
    """
    rows_raw = read_csv(path)
    if not rows_raw:
        return []

    rows = []
    for r in rows_raw:
        app = fix_encoding(r.get("App Name", r.get("Application", r.get("Name", ""))))
        date = ts_to_iso(r.get("Date", r.get("Created Date", r.get("First Use Date", ""))))
        if app:
            rows.append({
                "app_name":  app,
                "date":      date,
                "month":     date[:7] if date else "",
                "source":    "apple",
                "type":      "signin_with_apple",
            })
    return rows


def parse_calendar(path: Path) -> list:
    """
    Calendar Metadata.json
    Métadonnées des calendriers : nom, timezone, nb événements (storage)
    Pas les événements eux-mêmes (trop personnels)
    """
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []

    if not isinstance(data, list):
        data = [data]

    rows = []
    for cal in data:
        name = fix_encoding(cal.get("Calendar Display Name", ""))
        tz   = fix_encoding(cal.get("Calendar User Timezone", ""))
        ts   = cal.get("Calendar Collection Timestamp", "")
        mod  = cal.get("Calendar Collection  Modified by User Timestamp", "")
        storage = cal.get("Calendar Collection Total Storage", "")

        rows.append({
            "calendar_name":    name[:100],
            "timezone":         tz,
            "created":          ts_to_iso(ts) if ts else "",
            "last_modified":    ts_to_iso(mod) if mod else "",
            "storage_bytes":    storage,
            "source":           "apple",
            "type":             "calendar",
        })
    return rows


def parse_marketing(path: Path) -> list:
    """
    Marketing Communications Delivery.csv
    Quels types de communications marketing Apple t'envoie
    (pas les contenus, juste les catégories)
    """
    rows_raw = read_csv(path)
    if not rows_raw:
        return []

    rows = []
    for r in rows_raw:
        date = ts_to_iso(next((r.get(k, "") for k in r if "date" in k.lower()), ""))
        category = clean(next((r.get(k, "") for k in r if "category" in k.lower() or "type" in k.lower()), ""))
        status   = clean(next((r.get(k, "") for k in r if "status" in k.lower() or "delivery" in k.lower()), ""))
        if category or status:
            rows.append({
                "date":     date,
                "month":    date[:7] if date else "",
                "category": fix_encoding(category),
                "status":   fix_encoding(status),
                "source":   "apple",
                "type":     "marketing",
            })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Parser Apple — MyDigitalTwin")
    ap.add_argument("--input",  required=True, help="Dossier racine APPLE")
    ap.add_argument("--output", default="./data/processed/apple")
    args = ap.parse_args()

    root = Path(args.input)
    out  = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  MyDigitalTwin — Parser Apple")
    print(f"  Source : {root}")
    print(f"  Sortie : {out}")
    print(f"{'='*55}\n")

    stats = {}

    # ── App Install Activity ─────────────────────────────────────────────────
    print("📱 App Install Activity")
    p = root / "AppInstallActivity" / "App Install Activity.csv"
    if p.exists():
        rows = parse_app_installs(p)
        stats["app_installs"] = write_csv(rows, out / "app_installs.csv")
        if rows:
            # Stats rapides
            apps   = set(r["app_name"] for r in rows)
            years  = sorted(set(r["event_year"] for r in rows if r["event_year"]))
            types  = {}
            for r in rows:
                types[r["installation_type"]] = types.get(r["installation_type"], 0) + 1
            print(f"     {len(apps)} apps distinctes · {years[0] if years else '?'} → {years[-1] if years else '?'}")
            for t, n in sorted(types.items(), key=lambda x: -x[1]):
                print(f"     {t or 'inconnu':<20} : {n}")
    else:
        print(f"  [!] Introuvable : {p}")

    # ── Devices ─────────────────────────────────────────────────────────────
    print("\n📱 Appareils")
    p = root / "AppleAccountInformation" / "Apple ID Device Information.csv"
    if p.exists():
        rows = parse_devices(p)
        stats["devices"] = write_csv(rows, out / "devices.csv")
        if rows:
            models = set(r["device_model"] for r in rows if r["device_model"])
            print(f"     Appareils : {', '.join(sorted(models)[:8])}")
    else:
        print(f"  [!] Introuvable : {p}")

    # ── Sign In with Apple ───────────────────────────────────────────────────
    print("\n🔑 Sign In with Apple")
    p = root / "AppleAccountInformation" / "Apps Using Sign In with Apple.csv"
    if p.exists():
        stats["signin_apps"] = write_csv(parse_signin_apps(p), out / "signin_apps.csv")
    else:
        print(f"  [!] Introuvable : {p}")

    # ── Calendriers ─────────────────────────────────────────────────────────
    print("\n📅 Calendriers")
    p = root / "Calendriers et rappels iCloud" / "Calendar Metadata.json"
    if p.exists():
        stats["calendars"] = write_csv(parse_calendar(p), out / "calendars.csv")
    else:
        print(f"  [!] Introuvable : {p}")

    # ── Marketing ────────────────────────────────────────────────────────────
    print("\n📧 Communications marketing")
    p = root / "Communications marketing" / "Marketing Communications Delivery.csv"
    if p.exists():
        stats["marketing"] = write_csv(parse_marketing(p), out / "marketing.csv")
    else:
        print(f"  [!] Introuvable : {p}")

    # ── Résumé ───────────────────────────────────────────────────────────────
    total = sum(v for v in stats.values() if isinstance(v, int))
    print(f"\n{'─'*55}")
    print(f"  Total : {total:,} lignes dans {len([v for v in stats.values() if v])} fichiers")
    print(f"  Sortie: {out}")
    print(f"{'─'*55}")


if __name__ == "__main__":
    main()