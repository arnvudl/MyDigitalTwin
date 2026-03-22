"""
MyDigitalTwin — Parser TikTok & Twitter/X
==========================================
Deux parsers dans un seul fichier.

TikTok : un seul fichier JSON (~35Mo), toutes les données dedans.
Twitter : fichiers .js avec window.YTD.xxx = [...] en tête.

Usage :
    python tiktok_twitter_parser.py \\
        --tiktok  ./data/raw/TIKTOK/user_data.json \\
        --twitter ./data/raw/X/data \\
        --output  ./data/processed
"""

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES COMMUNS
# ══════════════════════════════════════════════════════════════════════════════

def fix_encoding(text: str) -> str:
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def anonymize(value: str, salt: str = "mydigitaltwin_2025") -> str:
    h = hashlib.sha256(f"{salt}{value}".encode()).hexdigest()[:10]
    return f"user_{h}"


def ts_to_iso(ts) -> str:
    if not ts:
        return ""
    try:
        v = float(str(ts).strip())
        if v > 1e10:
            v /= 1000
        return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        # Essayer le format string direct
        for fmt in [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%a %b %d %H:%M:%S %z %Y",  # Twitter: "Mon Jan 01 12:00:00 +0000 2024"
        ]:
            try:
                dt = datetime.strptime(str(ts).strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                continue
        return str(ts)


def ts_fields(iso: str) -> dict:
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
    except (ValueError, TypeError):
        return {"hour": "", "weekday": "", "month": "", "year": ""}


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


def get_nested(data: dict, *keys, default=""):
    """Accès sécurisé à un chemin imbriqué dans un dict."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data if data is not None else default


# ══════════════════════════════════════════════════════════════════════════════
# TIKTOK PARSER
# ══════════════════════════════════════════════════════════════════════════════

def load_tiktok(path: Path) -> dict:
    """Charge le JSON TikTok (~35Mo) avec gestion mémoire."""
    print(f"  → Chargement {path.name} ({path.stat().st_size / 1e6:.1f} Mo)…")
    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            return json.loads(path.read_text(encoding=enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    print(f"  [!] Impossible de lire {path.name}")
    return {}


def parse_tiktok_video_history(data: dict) -> list:
    """Your Activity > Watch History > VideoList"""
    items = get_nested(data, "Your Activity", "Watch History", "VideoList", default=[])
    rows = []
    for item in items:
        ts = ts_to_iso(item.get("Date", ""))
        url = item.get("Link", "")
        fields = ts_fields(ts)
        rows.append({
            "timestamp": ts,
            "hour": fields["hour"],
            "weekday": fields["weekday"],
            "month": fields["month"],
            "year": fields["year"],
            "url": url[:200],
            "type": "video_view",
            "platform": "tiktok",
        })
    return rows


def parse_tiktok_likes(data: dict) -> list:
    """Likes and Favorites > Like List > ItemFavoriteList"""
    items = get_nested(data, "Likes and Favorites", "Like List", "ItemFavoriteList", default=[])
    rows = []
    for item in items:
        ts = ts_to_iso(item.get("Date", ""))
        url = item.get("Link", "")
        fields = ts_fields(ts)
        rows.append({
            "timestamp": ts,
            "hour": fields["hour"],
            "weekday": fields["weekday"],
            "month": fields["month"],
            "year": fields["year"],
            "url": url[:200],
            "type": "like",
            "platform": "tiktok",
        })
    return rows


def parse_tiktok_searches(data: dict) -> list:
    """Your Activity > Searches > SearchList"""
    items = get_nested(data, "Your Activity", "Searches", "SearchList", default=[])
    rows = []
    for item in items:
        ts = ts_to_iso(item.get("Date", ""))
        query = fix_encoding(item.get("SearchTerm", ""))
        fields = ts_fields(ts)
        rows.append({
            "timestamp": ts,
            "hour": fields["hour"],
            "weekday": fields["weekday"],
            "month": fields["month"],
            "year": fields["year"],
            "query": query,
            "type": "search",
            "platform": "tiktok",
        })
    return rows


def parse_tiktok_comments(data: dict) -> list:
    """Comment.Comments — tes commentaires publics"""
    items = get_nested(data, "Comment", "Comments", "CommentsList", default=[])
    rows = []
    for item in items:
        ts = ts_to_iso(item.get("Date", ""))
        text = fix_encoding(item.get("Comment", ""))
        fields = ts_fields(ts)
        rows.append({
            "timestamp": ts,
            "hour": fields["hour"],
            "weekday": fields["weekday"],
            "month": fields["month"],
            "year": fields["year"],
            "text": text[:500],
            "char_count": len(text),
            "type": "comment",
            "platform": "tiktok",
        })
    return rows


def parse_tiktok_favorites(data: dict) -> list:
    """Activity.FavoriteVideos + FavoriteHashtags"""
    rows = []

    # Vidéos favorites
    videos = get_nested(data, "Likes and Favorites", "Favorite Videos", "FavoriteVideoList", default=[])
    for item in videos:
        ts = ts_to_iso(item.get("Date", ""))
        url = item.get("Link", "")
        fields = ts_fields(ts)
        rows.append({
            "timestamp": ts,
            "month": fields["month"],
            "year": fields["year"],
            "value": url[:200],
            "type": "favorite_video",
            "platform": "tiktok",
        })

    # Hashtags favoris
    hashtags = get_nested(data, "Likes and Favorites", "Favorite Hashtags", "FavoriteHashtagList", default=[])
    for item in hashtags:
        ts = ts_to_iso(item.get("Date", ""))
        tag = fix_encoding(item.get("HashtagName", item.get("HashtagLink", "")))
        fields = ts_fields(ts)
        rows.append({
            "timestamp": ts,
            "month": fields["month"],
            "year": fields["year"],
            "value": tag,
            "type": "favorite_hashtag",
            "platform": "tiktok",
        })

    return rows


def parse_tiktok_ads(data: dict) -> list:
    """Ads — profil publicitaire TikTok"""
    rows = []

    # Centres d'intérêt publicitaires
    interests = get_nested(data, "Your Activity", "Ad Interests", "AdInterestCategories", default=[])
    for item in interests:
        name = fix_encoding(item if isinstance(item, str) else item.get("Name", item.get("Category", "")))
        if name:
            rows.append({
                "type": "ad_interest",
                "value": name,
                "platform": "tiktok",
                "source": "tiktok_algo",
            })

    # Off-TikTok activity (sites/apps qui ont partagé tes données avec TikTok)
    off = get_nested(data, "Profile And Settings", "Off TikTok Activity", "OffTikTokActivityDataList", default=[])
    if not off:
        off = get_nested(data, "Your Activity", "Off TikTok Activity", "OffTikTokActivityDataList", default=[])
    for item in off:
        name = fix_encoding(item.get("Source", item.get("AppName", "")))
        if name:
            rows.append({
                "type": "off_platform_tracking",
                "value": name[:200],
                "platform": "tiktok",
                "source": "off_tiktok",
            })

    return rows


def parse_tiktok_network(data: dict) -> list:
    """Followers + Following (anonymisés)"""
    rows = []

    followers = get_nested(data, "Profile And Settings", "Follower", "FansList", default=[])
    for item in followers:
        name = item if isinstance(item, str) else item.get("FanNickName", "")
        rows.append({
            "user_anon": anonymize(name) if name else "",
            "relation": "follower",
            "platform": "tiktok",
        })

    following = get_nested(data, "Profile And Settings", "Following", "Following", default=[])
    for item in following:
        name = item if isinstance(item, str) else item.get("FollowingNickName", "")
        rows.append({
            "user_anon": anonymize(name) if name else "",
            "relation": "following",
            "platform": "tiktok",
        })

    return rows


# ══════════════════════════════════════════════════════════════════════════════
# TWITTER/X PARSER
# ══════════════════════════════════════════════════════════════════════════════

def load_twitter_js(path: Path):
    """
    Les fichiers .js Twitter ont la forme:
    window.YTD.tweets.part0 = [...]
    On strip la partie JS et on parse le JSON.
    """
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        # Retirer l'assignation JS : "window.YTD.xxx = "
        content = re.sub(r'^window\.YTD\.\w+\.\w+\s*=\s*', '', content.strip())
        return json.loads(content)
    except Exception as e:
        print(f"  [!] {path.name}: {e}")
        return None


def parse_twitter_tweets(data_dir: Path) -> list:
    """
    tweets.js — tous tes tweets
    Conserve : texte, date, métriques, langue
    """
    raw = load_twitter_js(data_dir / "tweets.js")
    if not raw:
        return []

    rows = []
    for entry in raw:
        tweet = entry.get("tweet", entry)
        ts = ts_to_iso(tweet.get("created_at", ""))
        text = fix_encoding(tweet.get("full_text", tweet.get("text", "")))
        fields = ts_fields(ts)

        # Retirer les @mentions du début (replies)
        clean_text = re.sub(r'^(@\w+\s*)+', '', text).strip()

        rows.append({
            "tweet_id": tweet.get("id_str", ""),
            "timestamp": ts,
            "hour": fields["hour"],
            "weekday": fields["weekday"],
            "month": fields["month"],
            "year": fields["year"],
            "text": clean_text[:500],
            "char_count": len(clean_text),
            "lang": tweet.get("lang", ""),
            "retweet_count": tweet.get("retweet_count", 0),
            "favorite_count": tweet.get("favorite_count", 0),
            "is_retweet": text.startswith("RT @"),
            "is_reply": bool(tweet.get("in_reply_to_status_id_str")),
            "has_media": bool(tweet.get("entities", {}).get("media")),
            "platform": "twitter",
            "type": "tweet",
        })
    return rows


def parse_twitter_likes(data_dir: Path) -> list:
    """like.js — tweets likés"""
    raw = load_twitter_js(data_dir / "like.js")
    if not raw:
        return []

    rows = []
    for entry in raw:
        like = entry.get("like", entry)
        rows.append({
            "tweet_id": like.get("tweetId", ""),
            "url": like.get("expandedUrl", "")[:200],
            "type": "like",
            "platform": "twitter",
        })
    return rows


def parse_twitter_followers(data_dir: Path) -> list:
    """follower.js + following.js — réseau anonymisé"""
    rows = []

    for filename, relation in [("follower.js", "follower"), ("following.js", "following")]:
        raw = load_twitter_js(data_dir / filename)
        if not raw:
            continue
        for entry in raw:
            item = entry.get(relation, entry)
            uid = item.get("accountId", item.get("userLink", ""))
            rows.append({
                "user_anon": anonymize(str(uid)) if uid else "",
                "relation": relation,
                "platform": "twitter",
            })

    return rows


def parse_twitter_dms(data_dir: Path) -> list:
    """
    direct-messages.js + direct-messages-group.js
    Métadonnées uniquement — contenu jamais stocké.
    """
    rows = []

    for filename, is_group in [
        ("direct-messages.js", False),
        ("direct-messages-group.js", True),
    ]:
        raw = load_twitter_js(data_dir / filename)
        if not raw:
            continue

        for entry in raw:
            conv = entry.get("dmConversation", entry)
            conv_id = anonymize(conv.get("conversationId", ""))
            messages = conv.get("messages", [])

            for msg_entry in messages:
                msg = msg_entry.get("messageCreate", msg_entry)
                ts = ts_to_iso(msg.get("createdAt", ""))
                text = msg.get("text", "")
                fields = ts_fields(ts)

                rows.append({
                    "conversation_id": conv_id,
                    "timestamp": ts,
                    "hour": fields["hour"],
                    "weekday": fields["weekday"],
                    "month": fields["month"],
                    "message_length": len(text),
                    "is_group": is_group,
                    "has_media": bool(msg.get("mediaUrls")),
                    "platform": "twitter",
                    "type": "dm",
                })

    return rows


def parse_twitter_ads(data_dir: Path) -> list:
    """ad-engagements.js + ad-impressions.js + personalization.js"""
    rows = []

    # Engagements publicitaires
    raw = load_twitter_js(data_dir / "ad-engagements.js")
    if raw:
        for entry in raw:
            ad = entry.get("ad", entry)
            impressions = ad.get("adsUserData", {}).get("adEngagements", {}).get("engagements", [])
            for imp in impressions:
                attrs = imp.get("impressionAttributes", {})
                ts = ts_to_iso(attrs.get("startTime", ""))
                fields = ts_fields(ts)
                rows.append({
                    "timestamp": ts,
                    "month": fields["month"],
                    "year": fields["year"],
                    "advertiser": attrs.get("advertiserName", "")[:100],
                    "display_type": attrs.get("displayLocation", ""),
                    "value": "",
                    "type": "ad_engagement",
                    "platform": "twitter",
                })

    # Centres d'intérêt (personalization.js)
    raw = load_twitter_js(data_dir / "personalization.js")
    if raw:
        for entry in raw:
            p14n = entry.get("p13nData", entry)
            interests = p14n.get("interests", {}).get("interests", [])
            for interest in interests:
                name = fix_encoding(interest.get("name", ""))
                if name:
                    rows.append({
                        "timestamp": "",
                        "month": "",
                        "year": "",
                        "advertiser": "",
                        "display_type": "",
                        "value": name,
                        "type": "ad_interest",
                        "platform": "twitter",
                    })

    return rows


def parse_twitter_saved_searches(data_dir: Path) -> list:
    """saved-search.js"""
    raw = load_twitter_js(data_dir / "saved-search.js")
    if not raw:
        return []
    rows = []
    for entry in raw:
        ss = entry.get("saved_search", entry)
        rows.append({
            "query": fix_encoding(ss.get("query", "")),
            "platform": "twitter",
            "type": "saved_search",
        })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Parser TikTok & Twitter — MyDigitalTwin")
    ap.add_argument("--tiktok", default=None, help="Chemin vers user_data.json TikTok")
    ap.add_argument("--twitter", default=None, help="Chemin vers le dossier data/ de Twitter/X")
    ap.add_argument("--output", default="./data/processed")
    args = ap.parse_args()

    print(f"\n{'=' * 55}")
    print(f"  MyDigitalTwin — Parser TikTok & Twitter/X")
    print(f"  Sortie : {args.output}")
    print(f"{'=' * 55}\n")

    stats = {}

    # ── TikTok ───────────────────────────────────────────────────────────────
    if args.tiktok:
        tiktok_out = Path(args.output) / "tiktok"
        print("🎵 TikTok")
        tdata = load_tiktok(Path(args.tiktok))

        if tdata:
            stats["tt_views"] = write_csv(parse_tiktok_video_history(tdata), tiktok_out / "tiktok_views.csv")
            stats["tt_likes"] = write_csv(parse_tiktok_likes(tdata), tiktok_out / "tiktok_likes.csv")
            stats["tt_searches"] = write_csv(parse_tiktok_searches(tdata), tiktok_out / "tiktok_searches.csv")
            stats["tt_comments"] = write_csv(parse_tiktok_comments(tdata), tiktok_out / "tiktok_comments.csv")
            stats["tt_favorites"] = write_csv(parse_tiktok_favorites(tdata), tiktok_out / "tiktok_favorites.csv")
            stats["tt_ads"] = write_csv(parse_tiktok_ads(tdata), tiktok_out / "tiktok_ads.csv")
            stats["tt_network"] = write_csv(parse_tiktok_network(tdata), tiktok_out / "tiktok_network.csv")
        else:
            print("  [!] Fichier TikTok vide ou illisible")

    # ── Twitter/X ────────────────────────────────────────────────────────────
    if args.twitter:
        twitter_out = Path(args.output) / "twitter"
        data_dir = Path(args.twitter)
        print("\n🐦 Twitter / X")

        stats["tw_tweets"] = write_csv(parse_twitter_tweets(data_dir), twitter_out / "tweets.csv")
        stats["tw_likes"] = write_csv(parse_twitter_likes(data_dir), twitter_out / "twitter_likes.csv")
        stats["tw_network"] = write_csv(parse_twitter_followers(data_dir), twitter_out / "twitter_network.csv")
        stats["tw_dms"] = write_csv(parse_twitter_dms(data_dir), twitter_out / "twitter_dms.csv")
        stats["tw_ads"] = write_csv(parse_twitter_ads(data_dir), twitter_out / "twitter_ads.csv")
        stats["tw_searches"] = write_csv(parse_twitter_saved_searches(data_dir), twitter_out / "twitter_searches.csv")

    # ── Résumé ───────────────────────────────────────────────────────────────
    total = sum(v for v in stats.values() if isinstance(v, int))
    print(f"\n{'─' * 55}")
    print(f"  Total : {total:,} lignes dans {len([v for v in stats.values() if v])} fichiers")
    print(f"{'─' * 55}")


if __name__ == "__main__":
    main()
