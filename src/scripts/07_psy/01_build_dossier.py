"""
07_psy / 01_build_dossier.py
Génère un package ZIP "Dossier Clinique Numérique" depuis le warehouse.

Usage:
    python src/scripts/07_psy/01_build_dossier.py \
        --start 2024-01-01 --end 2025-12-31 \
        --sources verbe inconscient emotionnel materiel \
        --anon-names --output output/Dossier_Psy_Arnaud.zip
"""

import argparse
import io
import json
import os
import re
import zipfile
from datetime import datetime

import pandas as pd

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE = "/app/data/warehouse" if os.path.exists("/app/data/warehouse") else "data/warehouse"
LLM_DATA_PATH = "/app/data/LLM_DATA/dataset_final.jsonl" if os.path.exists("/app/data/LLM_DATA") \
    else "data/LLM_DATA/dataset_final.jsonl"

FIRST_NAMES = [
    "Alice", "Nana", "Lou", "Maelle", "Evan", "Pilou", "Laura", "Jen",
    "Loulou", "Laure", "Gabi", "Mylene", "Fafie", "Ama", "Eliott", "Paulina",
    "Celia", "Vic", "Romane", "Djyoyo", "Léa", "Emma", "Hugo", "Théo",
    "Lucas", "Chloé", "Inès", "Jade", "Noah", "Léo",
]

REASONING_MARKERS = ["parce que", "du coup", "je pense", "en vrai", "en fait",
                     "donc", "c'est que", "ça veut dire", "au final", "genre"]
VERBAL_TICS = ["jsp", "bah", "oe", "mdr", "lol", "wtf", "pk", "ouais", "nan", "wsh"]

PSY_CATEGORIES = {
    "Santé / Corps": ["maladie", "symptôme", "douleur", "médecin", "fatigue", "anxiété",
                      "stress", "dépression", "sommeil", "santé", "kiné", "psy"],
    "Tech / IA": ["python", "ia", "llm", "gpt", "machine learning", "code", "github",
                  "docker", "data", "algorithme", "neural", "openai"],
    "Questions existentielles": ["sens de la vie", "bonheur", "solitude", "mort", "avenir",
                                  "identité", "liberté", "relation", "amour", "but"],
    "Finance / Carrière": ["salaire", "emploi", "stage", "argent", "budget", "investissement",
                            "bourse", "crypto", "entreprise", "startup"],
    "Divertissement": ["film", "série", "musique", "concert", "jeu", "sport", "netflix",
                       "spotify", "youtube", "anime"],
}


# ─── LOADERS ─────────────────────────────────────────────────────────────────

def _read_parquet(table: str, date_col: str = None,
                  start: str = None, end: str = None) -> pd.DataFrame:
    path = os.path.join(DELTA_BASE, table)
    if not os.path.exists(path):
        return pd.DataFrame()
    files = [os.path.join(path, f) for f in os.listdir(path)
             if f.endswith(".parquet") and not f.startswith(".")]
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    if date_col and start and end and date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[(df[date_col] >= pd.Timestamp(start)) &
                (df[date_col] <= pd.Timestamp(end))]
    return df


def _anonymize(text: str) -> str:
    """Remplace les prénoms connus par [PRÉNOM]."""
    if not isinstance(text, str):
        return text
    for name in FIRST_NAMES:
        text = re.sub(rf"\b{name}\b", "[PRÉNOM]", text, flags=re.IGNORECASE)
    return text


# ─── SECTION BUILDERS ────────────────────────────────────────────────────────

def _load_instagram_messages(anon_names: bool) -> pd.DataFrame:
    """Charge les messages Arnaud depuis data/LLM_DATA/dataset_final.jsonl."""
    if not os.path.exists(LLM_DATA_PATH):
        return pd.DataFrame()
    rows = []
    with open(LLM_DATA_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                ex = json.loads(line)
                for msg in ex.get("messages", []):
                    if msg.get("role") == "assistant":
                        text = msg.get("content", "").strip()
                        if text:
                            if anon_names:
                                text = _anonymize(text)
                            rows.append({"text": text, "platform": "instagram",
                                         "char_count": len(text), "word_count": len(text.split())})
            except Exception:
                continue
    return pd.DataFrame(rows)


def build_verbe(start: str, end: str, anon_names: bool) -> tuple[str, pd.DataFrame]:
    """Le Verbe — analyse des messages TikTok + Instagram (dataset_final.jsonl)."""
    tiktok_df = _read_parquet("tiktok_messages_text", "timestamp_ms", start, end)
    insta_df = _load_instagram_messages(anon_names)

    # Combiner les deux sources
    frames = []
    if not tiktok_df.empty:
        frames.append(tiktok_df[["text", "char_count", "word_count"]].assign(platform="tiktok"))
    if not insta_df.empty:
        frames.append(insta_df[["text", "char_count", "word_count", "platform"]])

    if not frames:
        return "## A. Le Verbe\n\n*Aucune donnée de messages disponible pour la période.*\n", pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    total_msgs = len(df)
    avg_len = df["char_count"].mean() if "char_count" in df.columns else df["text"].str.len().mean()
    avg_words = df["word_count"].mean() if "word_count" in df.columns else df["text"].str.split().str.len().mean()

    # Blocs de sincérité sur TikTok (qui a des timestamps)
    deep_sessions = pd.Series(dtype=int)
    if not tiktok_df.empty and "timestamp_ms" in tiktok_df.columns:
        tk = tiktok_df.copy()
        tk["timestamp_ms"] = pd.to_datetime(tk["timestamp_ms"], errors="coerce", unit="ms") \
            if tk["timestamp_ms"].dtype != "datetime64[ns]" else tk["timestamp_ms"]
        tk = tk.sort_values("timestamp_ms")
        tk["gap"] = tk["timestamp_ms"].diff().dt.total_seconds().fillna(0)
        tk["session"] = (tk["gap"] > 3600).cumsum()
        session_sizes = tk.groupby("session").size()
        deep_sessions = session_sizes[session_sizes >= 15]

    # Connecteurs de raisonnement
    reason_mask = df["text"].str.lower().apply(
        lambda t: any(m in str(t) for m in REASONING_MARKERS)
    )
    reason_count = reason_mask.sum()

    # Tics de langage
    tic_counts = {}
    for tic in VERBAL_TICS:
        count = df["text"].str.lower().str.count(rf"\b{tic}\b").sum()
        if count > 0:
            tic_counts[tic] = int(count)
    tic_counts = dict(sorted(tic_counts.items(), key=lambda x: -x[1])[:8])

    # Extraits représentatifs : messages avec connecteurs de raisonnement
    reason_df = df[reason_mask].dropna(subset=["text"])
    samples = []
    for _, row in reason_df.head(3).iterrows():
        sample = row["text"][:200]
        samples.append(f"> *\"{sample}{'...' if len(row['text']) > 200 else ''}\"*")

    sources_str = " + ".join(
        (["TikTok"] if not tiktok_df.empty else []) +
        (["Instagram"] if not insta_df.empty else [])
    )
    insta_count = len(insta_df) if not insta_df.empty else 0
    tiktok_count = len(tiktok_df) if not tiktok_df.empty else 0

    md = f"""## A. Le Verbe — Style & Psyché
*Sources : {sources_str} | Période TikTok : {start} → {end} | Instagram : corpus complet*

### Vue d'ensemble
- **Messages analysés :** {total_msgs:,} (Instagram : {insta_count:,}, TikTok : {tiktok_count:,})
- **Longueur moyenne :** {avg_len:.0f} caractères / {avg_words:.1f} mots
- **Sessions TikTok profondes (≥15 msgs consécutifs) :** {len(deep_sessions)}
- **Messages avec connecteurs de raisonnement :** {reason_count} ({100*reason_count/total_msgs:.1f}%)

### Tics de langage récurrents
{chr(10).join(f"- `{tic}` : {n} occurrences" for tic, n in tic_counts.items()) or "- Aucun tic significatif détecté"}

### Extraits — Blocs de sincérité
{chr(10).join(samples) or "*Pas de session profonde trouvée.*"}

"""
    # Timeline : utiliser les timestamps TikTok si disponibles
    if not tiktok_df.empty and "timestamp_ms" in tiktok_df.columns:
        timeline_df = tiktok_df[["timestamp_ms"]].copy().rename(columns={"timestamp_ms": "date"})
        timeline_df["section"] = "verbe"
    else:
        timeline_df = pd.DataFrame()
    return md, timeline_df


def build_inconscient(start: str, end: str) -> tuple[str, pd.DataFrame]:
    """L'Inconscient — recherches Google + YouTube."""
    goog = _read_parquet("google_searches", "event_date", start, end)
    yt = _read_parquet("youtube_searches", "event_date", start, end)

    rows = []
    if not goog.empty and "query" in goog.columns:
        rows += goog["query"].dropna().tolist()
    elif not goog.empty and "title" in goog.columns:
        rows += goog["title"].dropna().tolist()
    if not yt.empty and "title" in yt.columns:
        rows += yt["title"].dropna().tolist()

    if not rows:
        return "## B. L'Inconscient\n\n*Aucune donnée de recherches disponible.*\n", pd.DataFrame()

    total = len(rows)
    cat_counts = {}
    for cat, keywords in PSY_CATEGORIES.items():
        count = sum(
            any(kw in str(r).lower() for kw in keywords)
            for r in rows
        )
        if count > 0:
            cat_counts[cat] = count

    cat_counts = dict(sorted(cat_counts.items(), key=lambda x: -x[1]))
    top_queries = pd.Series(rows).value_counts().head(15).to_dict()

    md = f"""## B. L'Inconscient — Curiosité & Anxiété
*Source : Recherches Google + YouTube | Période : {start} → {end}*

### Volume
- **Recherches totales :** {total:,}

### Préoccupations par thématique
{chr(10).join(f"- **{cat}** : {n} recherches ({100*n/total:.1f}%)" for cat, n in cat_counts.items()) or "- Aucune catégorie identifiée"}

### Top 15 recherches les plus fréquentes
{chr(10).join(f"- `{q}` ({n}×)" for q, n in top_queries.items())}

"""
    timeline_df = pd.DataFrame({"date": rows, "section": "inconscient"})
    return md, timeline_df


def build_emotionnel(start: str, end: str) -> tuple[str, pd.DataFrame]:
    """L'Émotionnel — Spotify + Netflix + TikTok."""
    spotify = _read_parquet("spotify_streams", "listen_ts", start, end)
    netflix = _read_parquet("netflix_views", "watch_date", start, end)
    tiktok = _read_parquet("tiktok_watch", "event_date", start, end)

    md_parts = ["## C. L'Émotionnel — Mood & Divertissement\n"]
    timeline_rows = []

    # Spotify
    if not spotify.empty:
        total_min = spotify["minutes_played"].sum() if "minutes_played" in spotify.columns else 0
        top_artists = spotify["artistName"].value_counts().head(10).to_dict() if "artistName" in spotify.columns else {}
        night_pct = spotify["is_night"].mean() * 100 if "is_night" in spotify.columns else 0
        hour_dist = spotify.groupby("listen_hour").size() if "listen_hour" in spotify.columns else pd.Series()
        peak_hour = int(hour_dist.idxmax()) if not hour_dist.empty else 0

        md_parts.append(f"""### Spotify
*Période : {start} → {end}*
- **Écoutes totales :** {len(spotify):,} streams — {total_min:,.0f} minutes
- **Pic d'écoute :** {peak_hour}h — {night_pct:.0f}% la nuit (minuit–6h)
- **Top artistes :** {', '.join(f"{a} ({n})" for a, n in list(top_artists.items())[:5])}

""")
        if "listen_ts" in spotify.columns:
            tmp = spotify[["listen_ts"]].copy()
            tmp.columns = ["date"]
            tmp["section"] = "spotify"
            timeline_rows.append(tmp)

    # Netflix
    if not netflix.empty:
        total_views = len(netflix)
        top_shows = netflix["show_title"].value_counts().head(10).to_dict() if "show_title" in netflix.columns else {}
        binge_weeks = netflix.groupby("watch_week").size() if "watch_week" in netflix.columns else pd.Series()
        binge_week = int(binge_weeks.idxmax()) if not binge_weeks.empty else 0
        binge_n = int(binge_weeks.max()) if not binge_weeks.empty else 0

        md_parts.append(f"""### Netflix
- **Visionnages totaux :** {total_views:,}
- **Semaine de binge-watching record :** semaine {binge_week} ({binge_n} épisodes)
- **Top séries/films :** {', '.join(f"{s} ({n})" for s, n in list(top_shows.items())[:5])}

""")

    # TikTok watch
    if not tiktok.empty:
        total_tt = len(tiktok)
        night_tt = 0
        if "event_hour" in tiktok.columns:
            night_tt = (tiktok["event_hour"].between(0, 5)).mean() * 100
        md_parts.append(f"""### TikTok
- **Vidéos regardées :** {total_tt:,}
- **Visionnage nocturne (0h–6h) :** {night_tt:.0f}%

""")

    timeline_df = pd.concat(timeline_rows, ignore_index=True) if timeline_rows else pd.DataFrame()
    return "\n".join(md_parts), timeline_df


def build_materiel(start: str, end: str) -> tuple[str, pd.DataFrame]:
    """Le Matériel — Amazon."""
    df = _read_parquet("amazon_orders", "order_date", start, end)
    if df.empty:
        return "## D. Le Matériel\n\n*Aucune commande Amazon trouvée pour la période.*\n", pd.DataFrame()

    total_orders = len(df)
    total_spent = df["total_amount"].sum() if "total_amount" in df.columns else 0
    by_cat = df["category"].value_counts().head(10).to_dict() if "category" in df.columns else {}
    top_products = df["product_name"].value_counts().head(10).to_dict() if "product_name" in df.columns else {}

    md = f"""## D. Le Matériel — Priorités de Vie
*Source : Amazon Orders | Période : {start} → {end}*

### Vue d'ensemble
- **Commandes :** {total_orders:,}
- **Dépenses totales :** {total_spent:.2f} €

### Par catégorie
{chr(10).join(f"- **{cat}** : {n} commandes" for cat, n in by_cat.items()) or "- Catégories non disponibles"}

### Top produits
{chr(10).join(f"- {p} ({n}×)" for p, n in list(top_products.items())[:8])}

"""
    return md, df[["order_date", "total_amount", "category"]].rename(columns={"order_date": "date"}).assign(section="materiel") \
        if "order_date" in df.columns else (md, pd.DataFrame())


# ─── MAIN ────────────────────────────────────────────────────────────────────

def build_package(start: str, end: str, sources: list[str],
                  anon_names: bool, output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    sections_md = []
    timeline_dfs = []

    if "verbe" in sources:
        md, df = build_verbe(start, end, anon_names)
        sections_md.append(md)
        if not df.empty:
            timeline_dfs.append(df)

    if "inconscient" in sources:
        md, df = build_inconscient(start, end)
        sections_md.append(md)
        if not df.empty:
            timeline_dfs.append(df)

    if "emotionnel" in sources:
        md, df = build_emotionnel(start, end)
        sections_md.append(md)
        if not df.empty:
            timeline_dfs.append(df)

    if "materiel" in sources:
        md, df = build_materiel(start, end)
        sections_md.append(md)
        if not df.empty:
            timeline_dfs.append(df)

    # ── DOSSIER_PATIENT.md ─────────────────────────────────────────────────
    dossier = f"""# Dossier Clinique Numérique — Arnaud
*Généré le {datetime.now().strftime("%Y-%m-%d %H:%M")} | Période analysée : {start} → {end}*
*Sources incluses : {", ".join(sources)}*
{'*Anonymisation : prénoms remplacés par [PRÉNOM]*' if anon_names else ''}

---

{chr(10).join(sections_md)}
"""

    # ── CONSIGNE_ANALYSTE.md ───────────────────────────────────────────────
    consigne = """# Consigne pour l'Analyste IA

## Rôle
Tu es mon analyste **Lacanien-Amical**. Tu observes, tu questionnes, tu ne juges pas.

## Méthode
1. **Observation** : Commence par une corrélation surprenante entre deux sources de données.
2. **Questionnement** : Pose 2-3 questions ouvertes sur les contradictions que tu identifies.
3. **Lapsus Numérique** : Note les changements de comportement entre périodes ou plateformes.

## Interdictions
- Pas de reproches ni de leçons de vie
- Pas de ton moralisateur
- Pas de diagnostic clinique

## Structure de ta réponse
1. Une observation percutante d'ouverture (1 paragraphe)
2. Les paradoxes identifiés (liste de 3-5 points)
3. Tes questions (2-3 questions ouvertes)
4. Si une tendance complexe mérite visualisation : propose le code Python/Notebook correspondant

## Instruction d'amorce
Bonjour, je suis Arnaud. Voici mon dossier clinique numérique agrégé sur mes traces numériques.
Analyse les fichiers joints et commence la séance par une observation sur mes paradoxes ou mes évolutions de vie.
"""

    # ── TIMELINE_DATA.csv ──────────────────────────────────────────────────
    timeline_csv = ""
    if timeline_dfs:
        timeline = pd.concat(timeline_dfs, ignore_index=True)
        timeline["date"] = pd.to_datetime(timeline["date"], errors="coerce")
        timeline = timeline.dropna(subset=["date"]).sort_values("date")
        timeline_csv = timeline.to_csv(index=False)

    # ── ZIP ────────────────────────────────────────────────────────────────
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("DOSSIER_PATIENT.md", dossier.encode("utf-8"))
        zf.writestr("CONSIGNE_ANALYSTE.md", consigne.encode("utf-8"))
        if timeline_csv:
            zf.writestr("TIMELINE_DATA.csv", timeline_csv.encode("utf-8"))

    print(f"Package généré : {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--sources", nargs="+",
                        default=["verbe", "inconscient", "emotionnel", "materiel"])
    parser.add_argument("--anon-names", action="store_true")
    parser.add_argument("--output", default="output/Dossier_Psy_Arnaud.zip")
    args = parser.parse_args()
    build_package(args.start, args.end, args.sources, args.anon_names, args.output)
