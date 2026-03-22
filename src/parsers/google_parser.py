"""
MyDigitalTwin — Parser Google Takeout
=======================================
Parse les fichiers HTML (MonActivité.html) et JSON (Maps)
de l'export Google Takeout.

Fichiers traités :
    Recherche/MonActivité.html          → google_search.csv
    YouTube/MonActivité.html            → youtube_activity.csv
    historique youtube/watch-history.html → youtube_watch.csv
    historique youtube/Historique des recherches.html → youtube_search.csv
    Maps/MonActivité.html               → maps_activity.csv
    Chrome/MonActivité.html             → chrome_activity.csv
    Discover/MonActivité.html           → discover_activity.csv
    Vols+Voyage+Hôtels/MonActivité.html → travel_activity.csv
    Maps (vos adresses)/Adresses enregistrées.json → saved_places.csv
    Maps (vos adresses)/Avis.json       → maps_reviews.csv
    [tous les autres MonActivité.html]  → other_activity.csv

Format commun produit :
    timestamp | hour | weekday | month | year |
    activity_type | title | url | source | platform

Usage :
    python google_parser.py --input ./data/raw/GOOGLE --output ./data/processed/google
"""

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[!] BeautifulSoup requis : pip install beautifulsoup4 lxml")
    exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def fix_encoding(text: str) -> str:
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


# Mois français → numéro
MOIS_FR = {
    "janv": 1, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "août": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12,
    "jan": 1, "fev": 2, "jul": 7, "aout": 8
}


def parse_google_date(text: str) -> str:
    """
    Parse les dates Google Takeout en français.
    Ex: "15 janv. 2024, 14:32:05 UTC+1"
        "22 mars 2024 à 23:15:00 UTC+1"
    """
    if not text:
        return ""
    text = text.strip()

    # Pattern: "15 janv. 2024, 14:32:05 UTC+1" ou "22 mars 2024 à 23:15:00 UTC"
    m = re.search(
        r'(\d{1,2})\s+(\w+\.?)\s+(\d{4})[,\sà]+(\d{2}):(\d{2}):(\d{2})',
        text, re.IGNORECASE
    )
    if m:
        day, month_str, year, h, mi, s = m.groups()
        month_key = month_str.lower().rstrip('.')
        month_num = MOIS_FR.get(month_key[:4], None)
        if month_num:
            try:
                dt = datetime(int(year), month_num, int(day),
                              int(h), int(mi), int(s),
                              tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                pass

    # Pattern ISO fallback
    m2 = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', text)
    if m2:
        return m2.group(1)

    return ""


def ts_fields(iso: str) -> dict:
    """Décompose un timestamp ISO en champs analytiques."""
    if not iso:
        return {"hour": "", "weekday": "", "month": "", "year": ""}
    try:
        dt = datetime.fromisoformat(iso)
        return {
            "hour": dt.hour,
            "weekday": dt.weekday(),
            "month": dt.strftime("%Y-%m"),
            "year": dt.year,
        }
    except ValueError:
        return {"hour": "", "weekday": "", "month": "", "year": ""}


def extract_video_id(url: str) -> str:
    """Extrait l'ID YouTube d'une URL."""
    m = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else ""


def clean_url(url: str) -> str:
    """Garde uniquement la partie pertinente d'une URL."""
    if not url:
        return ""
    # Retirer les paramètres de tracking longs
    url = re.sub(r'&(utm_|ref=|hl=|gl=)[^&]*', '', url)
    return url[:300]


def write_csv(rows: list, path: Path) -> int:
    if not rows:
        print(f"  [~] Vide — {path.name}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [✓] {path.name:<45} {len(rows):>6} lignes")
    return len(rows)


# ══════════════════════════════════════════════════════════════════════════════
# PARSER HTML GOOGLE TAKEOUT (format commun)
# ══════════════════════════════════════════════════════════════════════════════

def parse_google_html(html_path: Path, activity_type: str, source: str) -> list:
    """
    Parser générique pour tous les fichiers MonActivité.html Google.
    Structure : div.outer-cell > div.content-cell
    """
    if not html_path.exists():
        return []

    try:
        content = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  [!] Erreur lecture {html_path.name}: {e}")
        return []

    # Correction double encodage
    content = fix_encoding(content)

    soup = BeautifulSoup(content, "lxml")
    cells = soup.find_all("div", class_="outer-cell")

    rows = []
    for cell in cells:
        content_div = cell.find("div", class_="content-cell")
        if not content_div:
            continue

        # Extraire tous les liens
        links = content_div.find_all("a")
        main_link = links[0] if links else None
        secondary_link = links[1] if len(links) > 1 else None

        title = fix_encoding(main_link.get_text(strip=True)) if main_link else ""
        url = clean_url(main_link.get("href", "")) if main_link else ""

        # Auteur / chaîne (YouTube)
        author = ""
        if secondary_link:
            href = secondary_link.get("href", "")
            if "channel" in href or "user" in href or "@" in href:
                author = fix_encoding(secondary_link.get_text(strip=True))

        # Extraire le timestamp (dernier texte sans lien dans le div)
        full_text = content_div.get_text(separator=" | ")
        timestamp = parse_google_date(full_text)

        if not title and not timestamp:
            continue

        fields = ts_fields(timestamp)
        row = {
            "timestamp": timestamp,
            "hour": fields["hour"],
            "weekday": fields["weekday"],
            "month": fields["month"],
            "year": fields["year"],
            "activity_type": activity_type,
            "title": title,
            "url": url,
            "author": author,
            "source": source,
            "platform": "google",
        }

        # Enrichissement spécifique YouTube
        if "youtube.com/watch" in url:
            row["video_id"] = extract_video_id(url)
        else:
            row["video_id"] = ""

        rows.append(row)

    return rows


# ══════════════════════════════════════════════════════════════════════════════
# PARSER JSON MAPS
# ══════════════════════════════════════════════════════════════════════════════

def parse_saved_places(path: Path) -> list:
    """
    Maps (vos adresses)/Adresses enregistrées.json
    Format GeoJSON FeatureCollection.
    Adresses domicile/travail anonymisées → label conservé, coordonnées supprimées.
    """
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []

    rows = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        date = props.get("date", "")
        label = fix_encoding(props.get("title", props.get("Comment", "")))
        url = props.get("google_maps_url", "")

        # Supprimer les coordonnées exactes (confidentialité)
        # On garde uniquement la date et le label du lieu
        rows.append({
            "timestamp": date,
            "month": date[:7] if date else "",
            "year": date[:4] if date else "",
            "label": label[:200],
            "maps_url": url[:200],
            "has_coords": False,  # coordonnées volontairement supprimées
            "platform": "google",
            "type": "saved_place",
        })

    return rows


def parse_maps_reviews(path: Path) -> list:
    """
    Maps (vos adresses)/Avis.json
    Tes avis Google Maps — texte conservé (tes propres mots publics).
    """
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []

    rows = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        date = props.get("date", props.get("published", ""))
        name = fix_encoding(props.get("name", props.get("Google Maps URL", "")))
        text = fix_encoding(props.get("Comment", props.get("review_text", "")))
        rating = props.get("star_rating", "")

        rows.append({
            "timestamp": date,
            "month": date[:7] if date else "",
            "place_name": name[:200],
            "review_text": text[:500],
            "rating": rating,
            "platform": "google",
            "type": "maps_review",
        })

    return rows


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

# Mapping fichiers → (activity_type, output_file, source_label)
HTML_FILES = [
    # (chemin relatif depuis root, activity_type, nom_output, source)
    ("Mon activit\u00e9 chez Google/Recherche/MonActivit\u00e9.html",
     "search", "google_search.csv", "Google Recherche"),

    ("Mon activit\u00e9 chez Google/YouTube/MonActivit\u00e9.html",
     "youtube_activity", "youtube_activity.csv", "YouTube activit\u00e9"),

    ("historique youtube (2023 - now)/watch-history.html",
     "youtube_watch", "youtube_watch.csv", "YouTube watch"),

    ("historique youtube (2023 - now)/Historique des recherches.html",
     "youtube_search", "youtube_search.csv", "YouTube recherche"),

    ("Mon activit\u00e9 chez Google/Chrome/MonActivit\u00e9.html",
     "chrome", "chrome_activity.csv", "Chrome"),

    ("Mon activit\u00e9 chez Google/Discover/MonActivit\u00e9.html",
     "discover", "discover_activity.csv", "Discover"),

    ("Mon activit\u00e9 chez Google/Maps/MonActivit\u00e9.html",
     "maps_search", "maps_activity.csv", "Maps"),

    ("Mon activit\u00e9 chez Google/Shopping/MonActivit\u00e9.html",
     "shopping", "shopping_activity.csv", "Shopping"),

    ("Mon activit\u00e9 chez Google/Google Play\u00a0Store/MonActivit\u00e9.html",
     "play_store", "play_store_activity.csv", "Play Store"),

    ("Mon activit\u00e9 chez Google/Google\u00a0Lens/MonActivit\u00e9.html",
     "lens", "lens_activity.csv", "Google Lens"),

    ("Mon activit\u00e9 chez Google/Vols/MonActivit\u00e9.html",
     "travel_flights", "travel_activity.csv", "Vols"),

    ("Mon activit\u00e9 chez Google/Voyage/MonActivit\u00e9.html",
     "travel_general", "travel_activity.csv", "Voyage"),

    ("Mon activit\u00e9 chez Google/H\u00f4tels/MonActivit\u00e9.html",
     "travel_hotels", "travel_activity.csv", "Hôtels"),

    ("Mon activit\u00e9 chez Google/Applications\u00a0Gemini/MonActivit\u00e9.html",
     "gemini", "gemini_activity.csv", "Gemini"),
]

# Fichiers à merger dans un seul "other_activity.csv"
OTHER_HTML = [
    "Android", "Aide", "Livres", "Google\u00a0TV",
    "Google\u00a0Actualit\u00e9s", "Google\u00a0Arts\u00a0&\u00a0Culture",
    "Google\u00a0Traduction", "Mode IA", "Recherche de vid\u00e9os",
    "Recherche d_images", "Assistant", "Voice\u00a0Match",
]


def main():
    ap = argparse.ArgumentParser(description="Parser Google Takeout — MyDigitalTwin")
    ap.add_argument("--input", required=True, help="Dossier racine GOOGLE")
    ap.add_argument("--output", default="./data/processed/google")
    args = ap.parse_args()

    root = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 55}")
    print(f"  MyDigitalTwin — Parser Google")
    print(f"  Source : {root}")
    print(f"  Sortie : {out}")
    print(f"{'=' * 55}\n")

    stats = {}
    totals = {}  # pour merger travel_activity

    # ── Fichiers HTML principaux ─────────────────────────────────────────────
    for rel_path, activity_type, out_name, source in HTML_FILES:
        html_path = root / rel_path
        rows = parse_google_html(html_path, activity_type, source)

        if out_name in totals:
            totals[out_name].extend(rows)
        else:
            totals[out_name] = rows

    # Écrire tous les fichiers (y compris les mergés)
    for out_name, rows in totals.items():
        section = out_name.replace(".csv", "")
        if section not in stats:
            stats[section] = 0
        stats[section] += write_csv(rows, out / out_name)

    # ── Autres activités (mergées) ───────────────────────────────────────────
    print("\n📦 Autres activités Google")
    other_rows = []
    for service in OTHER_HTML:
        p = root / f"Mon activit\u00e9 chez Google" / service / "MonActivit\u00e9.html"
        rows = parse_google_html(p, service.lower().replace(" ", "_"), service)
        other_rows.extend(rows)
    stats["other"] = write_csv(other_rows, out / "other_activity.csv")

    # ── Maps JSON ────────────────────────────────────────────────────────────
    print("\n🗺️  Maps (JSON)")
    stats["saved_places"] = write_csv(
        parse_saved_places(root / "Maps (vos adresses)" / "Adresses enregistr\u00e9es.json"),
        out / "saved_places.csv"
    )
    stats["maps_reviews"] = write_csv(
        parse_maps_reviews(root / "Maps (vos adresses)" / "Avis.json"),
        out / "maps_reviews.csv"
    )

    # ── Résumé ───────────────────────────────────────────────────────────────
    total = sum(v for v in stats.values() if isinstance(v, int))
    print(f"\n{'─' * 55}")
    print(f"  Total : {total:,} lignes dans {len([v for v in stats.values() if v])} fichiers")
    print(f"  Sortie: {out}")
    print(f"{'─' * 55}")


if __name__ == "__main__":
    main()
