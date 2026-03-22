"""
MyDigitalTwin — Parser Instagram
==================================
Lit tous les fichiers JSON Instagram et produit des DataFrames
pandas propres, anonymisés et prêts pour PySpark.

Structure produite dans data/processed/instagram/ :
    ads_clicked.csv
    ads_viewed.csv
    ads_categories.csv          ← ce que Meta pense que tu es
    advertisers.csv             ← qui achète tes données
    posts_viewed.csv
    videos_watched.csv
    likes_posts.csv
    likes_comments.csv
    comments.csv
    searches.csv
    saved_posts.csv
    story_likes.csv
    followers.csv
    following.csv
    close_friends.csv
    conversations_meta.csv      ← métadonnées inbox (JAMAIS le contenu)
    locations_of_interest.csv
    recommended_topics.csv
    link_history.csv

Usage:
    python instagram_parser.py --input ./raw/INSTAGRAM --output ./data/processed/instagram
"""

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def fix_encoding(text: str) -> str:
    """
    Corrige le double encodage UTF-8 présent dans les exports Instagram.
    Ex: "bibliothÃ¨que" → "bibliothèque"
    """
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def ts_to_iso(timestamp) -> str:
    """Convertit un timestamp Unix (secondes ou ms) en ISO 8601 UTC."""
    if not timestamp:
        return ""
    try:
        ts = float(timestamp)
        if ts == 0:
            return ""
        # Instagram utilise parfois des ms, parfois des secondes
        if ts > 1e10:
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return str(timestamp)


def anonymize(value: str, salt: str = "mydigitaltwin_2025") -> str:
    """Pseudonymise une valeur de manière reproductible."""
    h = hashlib.sha256(f"{salt}{value}".encode()).hexdigest()[:10]
    return f"user_{h}"


def load_json(path: Path):
    """Charge un JSON avec gestion d'encodage."""
    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    print(f"  [!] Impossible de lire : {path.name}")
    return None


def write_csv(rows: list, path: Path, label: str = ""):
    """Écrit une liste de dicts en CSV."""
    if not rows:
        print(f"  [~] Vide — {label or path.name}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    n = len(rows)
    print(f"  [✓] {path.name:<40} {n:>5} lignes")
    return n


def get_label_value(label_values: list, label: str) -> str:
    """Extrait une valeur par son label dans une liste label_values Instagram."""
    for item in label_values:
        if item.get("label") == label:
            return fix_encoding(item.get("value", "") or "")
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# PARSERS PAR FICHIER
# ══════════════════════════════════════════════════════════════════════════════

def parse_ads_clicked(path: Path) -> list:
    """
    ads_clicked.json
    Structure: liste d'objets avec timestamp + label_values
    Colonnes: timestamp, titre, url, advertiser_url
    """
    data = load_json(path)
    if not data:
        return []
    rows = []
    for item in data:
        lv = item.get("label_values", [])
        rows.append({
            "timestamp": ts_to_iso(item.get("timestamp")),
            "titre": get_label_value(lv, "Titre"),
            "url": get_label_value(lv, "URL"),
            "advertiser_url": get_label_value(lv, "URL publique de la bibliothèque publicitaire"),
            "platform": "instagram",
            "type": "ad_click"
        })
    return rows


def parse_ads_viewed(path: Path) -> list:
    """
    ads_viewed.json
    Structure identique à ads_clicked
    """
    data = load_json(path)
    if not data:
        return []
    rows = []
    for item in data:
        lv = item.get("label_values", [])
        rows.append({
            "timestamp": ts_to_iso(item.get("timestamp")),
            "titre": get_label_value(lv, "Titre"),
            "url": get_label_value(lv, "URL"),
            "platform": "instagram",
            "type": "ad_view"
        })
    return rows


def parse_ads_categories(path: Path) -> list:
    """
    other_categories_used_to_reach_you.json
    Structure: {label_values: [{label: "Nom", vec: [{value: "..."}]}]}
    Ce fichier révèle les catégories que Meta utilise pour te cibler.
    """
    data = load_json(path)
    if not data:
        return []
    rows = []
    for lv in data.get("label_values", []):
        if lv.get("label") == "Nom":
            for item in lv.get("vec", []):
                rows.append({
                    "category": fix_encoding(item.get("value", "")),
                    "platform": "instagram",
                    "source": "meta_targeting"
                })
    return rows


def parse_advertisers(path: Path) -> list:
    """
    advertisers_using_your_activity_or_information.json
    Liste des annonceurs qui ont utilisé tes données.
    """
    data = load_json(path)
    if not data:
        return []
    rows = []
    # Deux structures possibles selon la version de l'export
    items = data if isinstance(data, list) else data.get(
        "ig_custom_audiences_all_types", []
    )
    for item in items:
        if isinstance(item, dict):
            lv = item.get("label_values", [])
            name = get_label_value(lv, "Annonceur")
            if not name:
                name = fix_encoding(item.get("advertiser_name", ""))
            rows.append({
                "advertiser_name": name,
                "has_customer_file": get_label_value(lv, "A téléchargé une liste de clients"),
                "uses_remarketing": get_label_value(lv, "Utilise le pixel ou l'API"),
                "platform": "instagram"
            })
    return rows


def parse_posts_viewed(path: Path) -> list:
    """
    posts_viewed.json — posts organiques vus dans le feed
    """
    data = load_json(path)
    if not data:
        return []
    rows = []
    items = data if isinstance(data, list) else data.get("impressions_history_posts_seen", [])
    for item in items:
        lv = item.get("string_list_data", []) or item.get("label_values", [])
        ts = None
        author = ""
        if lv:
            ts = lv[0].get("timestamp") if isinstance(lv[0], dict) else None
            author = lv[0].get("value", "") if isinstance(lv[0], dict) else ""
        rows.append({
            "timestamp": ts_to_iso(ts),
            "author_anon": anonymize(author) if author else "",
            "platform": "instagram",
            "type": "post_view"
        })
    return rows


def parse_videos_watched(path: Path) -> list:
    """
    videos_watched.json
    """
    data = load_json(path)
    if not data:
        return []
    rows = []
    items = data if isinstance(data, list) else data.get("impressions_history_videos_watched", [])
    for item in items:
        lv = item.get("string_list_data", []) or item.get("label_values", [])
        ts = None
        author = ""
        if lv:
            ts = lv[0].get("timestamp") if isinstance(lv[0], dict) else None
            author = lv[0].get("value", "") if isinstance(lv[0], dict) else ""
        rows.append({
            "timestamp": ts_to_iso(ts),
            "author_anon": anonymize(author) if author else "",
            "platform": "instagram",
            "type": "video_view"
        })
    return rows


def parse_liked_posts(path: Path) -> list:
    """
    liked_posts.json
    Structure: {likes_media_likes: [{title, string_list_data: [{href, value, timestamp}]}]}
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("likes_media_likes", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        ts = sld[0].get("timestamp") if sld else None
        rows.append({
            "timestamp": ts_to_iso(ts),
            "platform": "instagram",
            "type": "like_post"
        })
    return rows


def parse_liked_comments(path: Path) -> list:
    """
    liked_comments.json
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("likes_comment_likes", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        ts = sld[0].get("timestamp") if sld else None
        rows.append({
            "timestamp": ts_to_iso(ts),
            "platform": "instagram",
            "type": "like_comment"
        })
    return rows


def parse_comments(post_path: Path, reels_path: Path) -> list:
    """
    post_comments_1.json + reels_comments.json
    Texte conservé — ce sont tes propres mots publics.
    """
    rows = []
    for fpath, ctype in [(post_path, "comment_post"), (reels_path, "comment_reel")]:
        data = load_json(fpath)
        if not data:
            continue
        items = data if isinstance(data, list) else data.get("comments_media_comments", [])
        for item in items:
            sld = item.get("string_list_data", [{}])
            ts = sld[0].get("timestamp") if sld else None
            text = fix_encoding(sld[0].get("value", "")) if sld else ""
            rows.append({
                "timestamp": ts_to_iso(ts),
                "text": text,
                "char_count": len(text),
                "platform": "instagram",
                "type": ctype
            })
    return rows


def parse_searches(path: Path) -> list:
    """
    word_or_phrase_searches.json
    Structure: {searches_keyword: [{string_map_data: {Recherche: {value, timestamp}, Heure: {timestamp}}}]}
    Note: timestamp=0 sur "Recherche", timestamp réel sur "Heure"
    """
    data = load_json(path)
    if not data:
        return []
    rows = []
    for item in data.get("searches_keyword", []):
        smd = item.get("string_map_data", {})
        query = fix_encoding(smd.get("Recherche", {}).get("value", ""))
        # Le vrai timestamp est dans "Heure"
        ts = smd.get("Heure", {}).get("timestamp") or smd.get("Recherche", {}).get("timestamp")
        rows.append({
            "timestamp": ts_to_iso(ts),
            "query": query,
            "platform": "instagram",
            "type": "search"
        })
    return rows


def parse_profile_searches(path: Path) -> list:
    """
    profile_searches.json — profils recherchés (anonymisés)
    """
    data = load_json(path)
    if not data:
        return []
    rows = []
    items = data if isinstance(data, list) else data.get("searches_user", [])
    for item in items:
        smd = item.get("string_map_data", {})
        name = smd.get("Recherche", {}).get("value", "") or smd.get("Profil", {}).get("value", "")
        ts = smd.get("Heure", {}).get("timestamp")
        rows.append({
            "timestamp": ts_to_iso(ts),
            "profile_anon": anonymize(name) if name else "",
            "platform": "instagram",
            "type": "profile_search"
        })
    return rows


def parse_saved_posts(path: Path) -> list:
    """
    saved_posts.json — posts sauvegardés = intérêts forts
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("saved_saved_media", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        ts = sld[0].get("timestamp") if sld else None
        rows.append({
            "timestamp": ts_to_iso(ts),
            "platform": "instagram",
            "type": "saved_post"
        })
    return rows


def parse_story_likes(path: Path) -> list:
    """
    story_likes.json
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("story_activities_story_likes", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        ts = sld[0].get("timestamp") if sld else None
        rows.append({
            "timestamp": ts_to_iso(ts),
            "platform": "instagram",
            "type": "story_like"
        })
    return rows


def parse_followers(path: Path) -> list:
    """
    followers_1.json — liste des abonnés avec timestamp de suivi
    Anonymisé.
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("relationships_followers", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        ts = sld[0].get("timestamp") if sld else None
        name = sld[0].get("value", "") if sld else ""
        rows.append({
            "timestamp": ts_to_iso(ts),
            "user_anon": anonymize(name) if name else "",
            "relation": "follower",
            "platform": "instagram"
        })
    return rows


def parse_following(path: Path) -> list:
    """
    following.json — liste des comptes suivis avec timestamp
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("relationships_following", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        ts = sld[0].get("timestamp") if sld else None
        name = sld[0].get("value", "") if sld else ""
        rows.append({
            "timestamp": ts_to_iso(ts),
            "user_anon": anonymize(name) if name else "",
            "relation": "following",
            "platform": "instagram"
        })
    return rows


def parse_close_friends(path: Path) -> list:
    """
    close_friends.json — liste des amis proches (anonymisés)
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("relationships_close_friends", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        name = sld[0].get("value", "") if sld else ""
        ts = sld[0].get("timestamp") if sld else None
        rows.append({
            "timestamp": ts_to_iso(ts),
            "user_anon": anonymize(name) if name else "",
            "relation": "close_friend",
            "platform": "instagram"
        })
    return rows


def parse_conversations_meta(inbox_path: Path, contacts_map: dict) -> list:
    """
    Parcourt inbox/ et extrait UNIQUEMENT les métadonnées.
    JAMAIS le contenu des messages.
    """
    rows = []
    for conv_dir in sorted(inbox_path.iterdir()):
        if not conv_dir.is_dir():
            continue

        raw_name = conv_dir.name
        anon_id = anonymize(raw_name)
        contacts_map[raw_name] = anon_id

        # Détection groupe via le nom (contient "and" ou chiffre > 2 dans "andX")
        is_group = bool(re.search(r'and\d+others', raw_name) or
                        re.search(r'\w+and\w+and', raw_name))

        msg_count = 0
        media_count = 0
        first_ts = None
        last_ts = None
        participants = set()

        for msg_file in sorted(conv_dir.glob("message_*.json")):
            data = load_json(msg_file)
            if not data:
                continue

            # Participants (anonymisés)
            for p in data.get("participants", []):
                pname = p.get("name", "")
                if pname:
                    participants.add(anonymize(pname))

            # Comptage messages — SANS lire le contenu
            for msg in data.get("messages", []):
                msg_count += 1

                ts = msg.get("timestamp_ms")
                if ts:
                    ts_sec = ts / 1000
                    if first_ts is None or ts_sec < first_ts:
                        first_ts = ts_sec
                    if last_ts is None or ts_sec > last_ts:
                        last_ts = ts_sec

                # Compter les médias par type
                for media_key in ["photos", "videos", "audio_files", "gifs", "files"]:
                    media_count += len(msg.get(media_key, []))

        rows.append({
            "conversation_id": anon_id,
            "is_group": is_group,
            "participants_count": len(participants),
            "message_count": msg_count,
            "media_count": media_count,
            "first_message": ts_to_iso(first_ts),
            "last_message": ts_to_iso(last_ts),
            "platform": "instagram"
        })

    return rows


def parse_locations_of_interest(path: Path) -> list:
    """
    locations_of_interest.json — lieux détectés par Instagram
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("inferred_data_ig_interest", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        value = sld[0].get("value", "") if sld else ""
        ts = sld[0].get("timestamp") if sld else None
        rows.append({
            "timestamp": ts_to_iso(ts),
            "location": fix_encoding(value),
            "platform": "instagram",
            "source": "inferred"
        })
    return rows


def parse_recommended_topics(path: Path) -> list:
    """
    recommended_topics.json — topics recommandés par l'algo
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("topics_your_topics", [])
    rows = []
    for item in items:
        sld = item.get("string_list_data", [{}])
        value = sld[0].get("value", "") if sld else ""
        rows.append({
            "topic": fix_encoding(value),
            "platform": "instagram",
            "source": "recommended"
        })
    return rows


def parse_link_history(path: Path) -> list:
    """
    link_history.json — liens cliqués
    """
    data = load_json(path)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("label_values", [])
    rows = []
    # Structure variable selon version export
    if isinstance(data, list):
        for item in data:
            lv = item.get("label_values", [])
            ts = item.get("timestamp")
            url = get_label_value(lv, "Lien") or get_label_value(lv, "URL")
            rows.append({
                "timestamp": ts_to_iso(ts),
                "url": url,
                "platform": "instagram",
                "type": "link_click"
            })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Parser Instagram — MyDigitalTwin")
    parser.add_argument("--input", required=True, help="Dossier Instagram exporté")
    parser.add_argument("--output", default="./data/processed/instagram")
    args = parser.parse_args()

    root = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═' * 55}")
    print(f"  MyDigitalTwin — Parser Instagram")
    print(f"  Source : {root}")
    print(f"  Sortie : {out}")
    print(f"{'═' * 55}\n")

    stats = {}
    contacts_map = {}

    # ── Publicités & algorithme ──────────────────────────────────────────────
    print("📢 Publicités & algorithme")
    stats["ads_clicked"] = write_csv(parse_ads_clicked(root / "ads_information/ads_and_topics/ads_clicked.json"),
                                     out / "ads_clicked.csv")
    stats["ads_viewed"] = write_csv(parse_ads_viewed(root / "ads_information/ads_and_topics/ads_viewed.json"),
                                    out / "ads_viewed.csv")
    stats["ads_categories"] = write_csv(parse_ads_categories(
        root / "ads_information/instagram_ads_and_businesses/other_categories_used_to_reach_you.json"),
                                        out / "ads_categories.csv")
    stats["advertisers"] = write_csv(parse_advertisers(
        root / "ads_information/instagram_ads_and_businesses/advertisers_using_your_activity_or_information.json"),
                                     out / "advertisers.csv")
    stats["posts_viewed"] = write_csv(parse_posts_viewed(root / "ads_information/ads_and_topics/posts_viewed.json"),
                                      out / "posts_viewed.csv")
    stats["videos_watched"] = write_csv(
        parse_videos_watched(root / "ads_information/ads_and_topics/videos_watched.json"), out / "videos_watched.csv")

    # ── Activité & engagement ────────────────────────────────────────────────
    print("\n❤️  Activité & engagement")
    stats["likes_posts"] = write_csv(parse_liked_posts(root / "your_instagram_activity/likes/liked_posts.json"),
                                     out / "likes_posts.csv")
    stats["likes_comments"] = write_csv(
        parse_liked_comments(root / "your_instagram_activity/likes/liked_comments.json"), out / "likes_comments.csv")
    stats["comments"] = write_csv(parse_comments(
        root / "your_instagram_activity/comments/post_comments_1.json",
        root / "your_instagram_activity/comments/reels_comments.json"
    ), out / "comments.csv")
    stats["saved_posts"] = write_csv(parse_saved_posts(root / "your_instagram_activity/saved/saved_posts.json"),
                                     out / "saved_posts.csv")
    stats["story_likes"] = write_csv(
        parse_story_likes(root / "your_instagram_activity/story_interactions/story_likes.json"),
        out / "story_likes.csv")

    # ── Recherches & navigation ──────────────────────────────────────────────
    print("\n🔎 Recherches & navigation")
    stats["searches"] = write_csv(
        parse_searches(root / "logged_information/recent_searches/word_or_phrase_searches.json"), out / "searches.csv")
    stats["profile_searches"] = write_csv(
        parse_profile_searches(root / "logged_information/recent_searches/profile_searches.json"),
        out / "profile_searches.csv")
    stats["link_history"] = write_csv(parse_link_history(root / "logged_information/link_history/link_history.json"),
                                      out / "link_history.csv")

    # ── Réseau social ────────────────────────────────────────────────────────
    print("\n👥 Réseau social")
    stats["followers"] = write_csv(parse_followers(root / "connections/followers_and_following/followers_1.json"),
                                   out / "followers.csv")
    stats["following"] = write_csv(parse_following(root / "connections/followers_and_following/following.json"),
                                   out / "following.csv")
    stats["close_friends"] = write_csv(
        parse_close_friends(root / "connections/followers_and_following/close_friends.json"), out / "close_friends.csv")

    # ── Messages (métadonnées uniquement) ────────────────────────────────────
    print("\n💬 Messages (métadonnées — contenu jamais lu)")
    inbox = root / "your_instagram_activity/messages/inbox"
    if inbox.exists():
        conv_rows = parse_conversations_meta(inbox, contacts_map)
        stats["conversations"] = write_csv(conv_rows, out / "conversations_meta.csv")
        # Sauvegarder le mapping contacts (NE PAS pusher sur GitHub)
        contacts_path = out / "contacts_map.json"
        with open(contacts_path, "w", encoding="utf-8") as f:
            json.dump(contacts_map, f, indent=2, ensure_ascii=False)
        print(f"  [🔐] contacts_map.json — {len(contacts_map)} contacts (⚠️ privé, dans .gitignore)")

    # ── Centres d'intérêt détectés ───────────────────────────────────────────
    print("\n🎯 Centres d'intérêt détectés par l'algo")
    stats["locations"] = write_csv(
        parse_locations_of_interest(root / "personal_information/information_about_you/locations_of_interest.json"),
        out / "locations_of_interest.csv")
    stats["topics"] = write_csv(parse_recommended_topics(root / "preferences/your_topics/recommended_topics.json"),
                                out / "recommended_topics.csv")

    # ── Résumé ───────────────────────────────────────────────────────────────
    total = sum(v for v in stats.values() if v)
    print(f"\n{'─' * 55}")
    print(f"✅ Terminé — {total:,} lignes produites dans {len(stats)} fichiers")
    print(f"\n📌 Prochaine étape :")
    print(f"   jupyter notebook → 01_exploration_instagram.ipynb")
    print(f"{'─' * 55}\n")


if __name__ == "__main__":
    main()
