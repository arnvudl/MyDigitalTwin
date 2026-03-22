"""
MyDigitalTwin — Timeline des messages Instagram
=================================================
Extrait une ligne par message avec uniquement des métadonnées.
Le contenu textuel N'EST JAMAIS stocké — uniquement la longueur en caractères.

Colonnes produites dans messages_timeline.csv :
    conversation_id     → ID anonyme de la conversation
    timestamp           → ISO 8601 UTC
    hour                → heure (0-23)
    weekday             → 0=lundi … 6=dimanche
    month               → YYYY-MM
    year                → YYYY
    sender              → "ME" ou "OTHER" (jamais le vrai nom)
    message_length      → nb de caractères (0 si média)
    media_type          → text | photo | video | audio | gif | unsent | other
    has_reaction        → True/False
    reaction_count      → nb de réactions reçues
    response_delay_sec  → délai de réponse en secondes (vide si non applicable)
    is_group            → True/False
    platform            → instagram

Usage:
    python messages_timeline_parser.py --input ./raw/INSTAGRAM/your_instagram_activity/messages/inbox
    python messages_timeline_parser.py --input ./raw/INSTAGRAM/your_instagram_activity/messages/inbox --my-name "Arnau"
"""

import json
import csv
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone


# ── Utilitaires ───────────────────────────────────────────────────────────────

def fix_encoding(text):
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def ts_to_iso(ms):
    if not ms:
        return ""
    try:
        sec = ms / 1000 if ms > 1e10 else float(ms)
        return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return ""


def anonymize(value, salt="mydigitaltwin_2025"):
    h = hashlib.sha256(f"{salt}{value}".encode()).hexdigest()[:10]
    return f"user_{h}"


def load_json(path):
    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            return json.loads(path.read_text(encoding=enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return None


# ── Détection du nom ─────────────────────────────────────────────────────────

def detect_my_name(inbox_path):
    """
    Détecte automatiquement ton nom en comptant les senders
    sur un échantillon de 25 conversations.
    """
    sender_count = {}
    sampled = 0
    for conv_dir in inbox_path.iterdir():
        if not conv_dir.is_dir() or sampled >= 25:
            break
        msg_file = conv_dir / "message_1.json"
        if not msg_file.exists():
            continue
        data = load_json(msg_file)
        if not data:
            continue
        for msg in data.get("messages", [])[:20]:
            s = fix_encoding(msg.get("sender_name", ""))
            if s:
                sender_count[s] = sender_count.get(s, 0) + 1
        sampled += 1

    if not sender_count:
        return None
    return max(sender_count, key=sender_count.get)


# ── Type de contenu ───────────────────────────────────────────────────────────

def get_media_type(msg):
    if msg.get("is_unsent"):
        return "unsent"
    if msg.get("photos"):
        return "photo"
    if msg.get("videos"):
        return "video"
    if msg.get("audio_files"):
        return "audio"
    if msg.get("gifs"):
        return "gif"
    if msg.get("content"):
        return "text"
    return "other"


# ── Parser principal ──────────────────────────────────────────────────────────

def parse_messages_timeline(inbox_path, my_name=None):
    inbox_path = Path(inbox_path)

    # Détection automatique du nom
    if not my_name:
        print("  → Détection automatique de ton nom…")
        my_name = detect_my_name(inbox_path)
        if my_name:
            print(f"  → Nom détecté : {my_name}")
        else:
            print("  [!] Nom non détecté — sender sera anonymisé (utilise --my-name)")

    rows = []
    conv_dirs   = [d for d in sorted(inbox_path.iterdir()) if d.is_dir()]
    total_convs = len(conv_dirs)

    for i, conv_dir in enumerate(conv_dirs, 1):
        conv_id   = anonymize(conv_dir.name)
        msg_files = sorted(conv_dir.glob("message_*.json"))

        all_messages = []
        participants = set()

        for msg_file in msg_files:
            data = load_json(msg_file)
            if not data:
                continue
            for p in data.get("participants", []):
                name = fix_encoding(p.get("name", ""))
                if name:
                    participants.add(name)
            for msg in data.get("messages", []):
                if msg.get("timestamp_ms"):
                    all_messages.append(msg)

        if not all_messages:
            continue

        is_group = len(participants) > 2
        all_messages.sort(key=lambda m: m.get("timestamp_ms", 0))

        prev_ts     = None
        prev_sender = None

        for msg in all_messages:
            ts_ms  = msg.get("timestamp_ms", 0)
            sender = fix_encoding(msg.get("sender_name", ""))
            is_me  = (sender == my_name) if my_name else False

            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

            # Délai de réponse (changement d'expéditeur uniquement)
            delay = ""
            if prev_ts and prev_sender and prev_sender != sender:
                d = round((ts_ms - prev_ts) / 1000)
                if 0 < d <= 86400:   # Ignorer > 24h
                    delay = d

            # Longueur message (texte uniquement, jamais le contenu)
            content = msg.get("content", "")
            msg_len = len(fix_encoding(content)) if (content and not msg.get("is_unsent")) else 0

            rows.append({
                "conversation_id":    conv_id,
                "timestamp":          ts_to_iso(ts_ms),
                "hour":               dt.hour,
                "weekday":            dt.weekday(),
                "month":              dt.strftime("%Y-%m"),
                "year":               dt.year,
                "sender":             "ME" if is_me else "OTHER",
                "message_length":     msg_len,
                "media_type":         get_media_type(msg),
                "has_reaction":       bool(msg.get("reactions")),
                "reaction_count":     len(msg.get("reactions", [])),
                "response_delay_sec": delay,
                "is_group":           is_group,
                "platform":           "instagram",
            })

            prev_ts     = ts_ms
            prev_sender = sender

        if i % 50 == 0 or i == total_convs:
            print(f"  → {i}/{total_convs} conversations ({len(rows):,} messages)…")

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Timeline messages Instagram — MyDigitalTwin")
    ap.add_argument("--input",   required=True,
                    help="Chemin vers inbox/ ex: ./raw/INSTAGRAM/your_instagram_activity/messages/inbox")
    ap.add_argument("--output",  default="./data/processed/instagram/messages_timeline.csv")
    ap.add_argument("--my-name", default=None,
                    help="Ton prénom exact tel qu'il apparaît dans Instagram (optionnel)")
    args = ap.parse_args()

    inbox  = Path(args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  MyDigitalTwin — Timeline des messages")
    print(f"  Source : {inbox}")
    print(f"  Sortie : {output}")
    print(f"{'='*55}\n")

    rows = parse_messages_timeline(inbox, my_name=args.my_name)

    if not rows:
        print("[!] Aucun message trouvé. Vérifie le chemin --input.")
        exit(1)

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # Résumé
    total      = len(rows)
    sent       = sum(1 for r in rows if r["sender"] == "ME")
    received   = total - sent
    with_media = sum(1 for r in rows if r["media_type"] != "text")
    months     = sorted(set(r["month"] for r in rows if r["month"]))

    print(f"\n{'─'*55}")
    print(f"  messages exportés : {total:,}")
    print(f"  envoyés (ME)      : {sent:,}  ({100*sent//total}%)")
    print(f"  reçus (OTHER)     : {received:,}  ({100*received//total}%)")
    print(f"  avec média        : {with_media:,}")
    if months:
        print(f"  période           : {months[0]} → {months[-1]}")
    print(f"  fichier           : {output}")
    print(f"{'─'*55}")