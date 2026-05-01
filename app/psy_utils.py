import json
import os
import re
import zipfile
from datetime import datetime
import pandas as pd

from config import (
    WAREHOUSE, LLM_DATA, DATA_ROOT,
    PSY_FIRST_NAMES, PSY_REASONING_MARKERS, PSY_VERBAL_TICS, PSY_BEHAVIOUR_CATEGORIES,
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DELTA_BASE        = WAREHOUSE
LLM_DATA_PATH     = os.path.join(LLM_DATA, "dataset_final.jsonl")
STATIC_PACKAGE_DIR = os.path.join(DATA_ROOT, "Analyse comportementaliste")

# Alias locaux pour la compatibilité des fonctions ci-dessous
FIRST_NAMES         = PSY_FIRST_NAMES
REASONING_MARKERS   = PSY_REASONING_MARKERS
VERBAL_TICS         = PSY_VERBAL_TICS
BEHAVIOUR_CATEGORIES = PSY_BEHAVIOUR_CATEGORIES


# ─── LOADERS ─────────────────────────────────────────────────────────────────

def _read_parquet(table: str, date_col: str = None, start: str = None, end: str = None) -> pd.DataFrame:
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
        df = df[(df[date_col] >= pd.Timestamp(start)) & (df[date_col] <= pd.Timestamp(end))]
    return df


def _anonymize(text: str) -> str:
    if not isinstance(text, str):
        return text
    for name in FIRST_NAMES:
        text = re.sub(rf"\b{name}\b", "[PRÉNOM]", text, flags=re.IGNORECASE)
    return text


def _load_instagram_from_warehouse(start: str, end: str, anon_names: bool) -> pd.DataFrame:
    """Charge les messages Instagram depuis le warehouse (table instagram_messages_text)."""
    df = _read_parquet("instagram_messages_text", "timestamp_ms", start, end)
    if df.empty:
        return pd.DataFrame()
    text_col = "text" if "text" in df.columns else (df.columns[0] if len(df.columns) else None)
    if not text_col:
        return pd.DataFrame()
    df = df.rename(columns={text_col: "text"})
    df["text"] = df["text"].astype(str)
    if anon_names:
        df["text"] = df["text"].apply(_anonymize)
    df["char_count"] = df["text"].str.len()
    df["word_count"] = df["text"].str.split().str.len()
    df["platform"] = "instagram"
    return df[["text", "char_count", "word_count", "platform"]]


def _load_instagram_from_llm_data(anon_names: bool) -> pd.DataFrame:
    """Fallback : charge les messages Arnaud depuis data/LLM_DATA/dataset_final.jsonl."""
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


# ─── SECTION BUILDERS ────────────────────────────────────────────────────────

def build_verbe(start: str, end: str, anon_names: bool):
    tiktok_df = _read_parquet("tiktok_messages_text", "timestamp_ms", start, end)

    # Instagram : warehouse en priorité, sinon LLM_DATA
    insta_warehouse = _load_instagram_from_warehouse(start, end, anon_names)
    insta_df = insta_warehouse if not insta_warehouse.empty else _load_instagram_from_llm_data(anon_names)
    insta_source = "warehouse" if not insta_warehouse.empty else "LLM_DATA"

    frames = []
    if not tiktok_df.empty:
        frames.append(tiktok_df[["text", "char_count", "word_count"]].assign(platform="tiktok"))
    if not insta_df.empty:
        frames.append(insta_df[["text", "char_count", "word_count", "platform"]])

    if not frames:
        return "## A. Le Verbe\n\n*Aucune donnée de messages disponible pour la période.*\n", pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    total_msgs = len(df)
    avg_len = df["char_count"].mean()
    avg_words = df["word_count"].mean()
    insta_count = len(insta_df) if not insta_df.empty else 0
    tiktok_count = len(tiktok_df) if not tiktok_df.empty else 0

    # Blocs de sincérité TikTok
    deep_sessions = pd.Series(dtype=int)
    if not tiktok_df.empty and "timestamp_ms" in tiktok_df.columns:
        tk = tiktok_df.copy()
        tk["timestamp_ms"] = pd.to_datetime(tk["timestamp_ms"], errors="coerce",
                                             unit="ms" if tk["timestamp_ms"].dtype != "datetime64[ns]" else None)
        tk = tk.sort_values("timestamp_ms")
        tk["gap"] = tk["timestamp_ms"].diff().dt.total_seconds().fillna(0)
        tk["session"] = (tk["gap"] > 3600).cumsum()
        deep_sessions = tk.groupby("session").size()
        deep_sessions = deep_sessions[deep_sessions >= 15]

    reason_mask = df["text"].str.lower().apply(
        lambda t: any(m in str(t) for m in REASONING_MARKERS)
    )
    reason_count = reason_mask.sum()

    tic_counts = {}
    for tic in VERBAL_TICS:
        c = df["text"].str.lower().str.count(rf"\b{tic}\b").sum()
        if c > 0:
            tic_counts[tic] = int(c)
    tic_counts = dict(sorted(tic_counts.items(), key=lambda x: -x[1])[:8])

    samples = []
    for _, row in df[reason_mask].head(3).iterrows():
        s = str(row["text"])[:200]
        samples.append(f"> *\"{s}{'...' if len(str(row['text'])) > 200 else ''}\"*")

    sources_str = " + ".join(
        (["TikTok"] if not tiktok_df.empty else []) +
        (["Instagram"] if not insta_df.empty else [])
    )
    insta_note = f"Instagram : {insta_count:,} msgs ({insta_source})"

    md = f"""## A. Le Verbe — Style & Communication
*Sources : {sources_str} | Période TikTok : {start} → {end} | {insta_note}*

### Vue d'ensemble
- **Messages analysés :** {total_msgs:,} (Instagram : {insta_count:,}, TikTok : {tiktok_count:,})
- **Longueur moyenne :** {avg_len:.0f} caractères / {avg_words:.1f} mots
- **Sessions TikTok profondes (≥15 msgs) :** {len(deep_sessions)}
- **Messages avec connecteurs de raisonnement :** {reason_count} ({100*reason_count/total_msgs:.1f}%)

### Tics de langage récurrents
{chr(10).join(f"- `{tic}` : {n} occurrences" for tic, n in tic_counts.items()) or "- Aucun tic significatif détecté"}

### Extraits représentatifs
{chr(10).join(samples) or "*Pas d'extrait trouvé.*"}

"""
    return md, pd.DataFrame()


def build_inconscient(start: str, end: str):
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
    for cat, keywords in BEHAVIOUR_CATEGORIES.items():
        count = sum(any(kw in str(r).lower() for kw in keywords) for r in rows)
        if count > 0:
            cat_counts[cat] = count
    cat_counts = dict(sorted(cat_counts.items(), key=lambda x: -x[1]))
    top_queries = pd.Series(rows).value_counts().head(15).to_dict()

    md = f"""## B. L'Inconscient — Curiosité & Préoccupations
*Sources : Recherches Google + YouTube | Période : {start} → {end}*

### Volume
- **Recherches totales :** {total:,}

### Thématiques dominantes
{chr(10).join(f"- **{cat}** : {n} ({100*n/total:.1f}%)" for cat, n in cat_counts.items()) or "- Aucune catégorie identifiée"}

### Top 15 recherches les plus fréquentes
{chr(10).join(f"- `{q}` ({n}×)" for q, n in top_queries.items())}

"""
    return md, pd.DataFrame()


def build_emotionnel(start: str, end: str):
    spotify = _read_parquet("spotify_streams", "listen_ts", start, end)
    netflix = _read_parquet("netflix_views", "watch_date", start, end)
    tiktok = _read_parquet("tiktok_watch", "event_date", start, end)

    md_parts = ["## C. L'Émotionnel — Mood & Divertissement\n"]

    if not spotify.empty:
        total_min = spotify["minutes_played"].sum() if "minutes_played" in spotify.columns else 0
        top_artists = spotify["artistName"].value_counts().head(5).to_dict() if "artistName" in spotify.columns else {}
        night_pct = spotify["is_night"].mean() * 100 if "is_night" in spotify.columns else 0
        hour_dist = spotify.groupby("listen_hour").size() if "listen_hour" in spotify.columns else pd.Series()
        peak_hour = int(hour_dist.idxmax()) if not hour_dist.empty else 0

        md_parts.append(f"""### Spotify
- **Écoutes :** {len(spotify):,} streams ({total_min:,.0f} min)
- **Pic d'écoute :** {peak_hour}h — {night_pct:.0f}% nocturne (minuit–6h)
- **Top artistes :** {', '.join(f"{a} ({n})" for a, n in top_artists.items()) or "n/a"}

""")

    if not netflix.empty:
        binge_weeks = netflix.groupby("watch_week").size() if "watch_week" in netflix.columns else pd.Series()
        binge_week = int(binge_weeks.idxmax()) if not binge_weeks.empty else 0
        binge_n = int(binge_weeks.max()) if not binge_weeks.empty else 0
        top_shows = netflix["show_title"].value_counts().head(5).to_dict() if "show_title" in netflix.columns else {}
        md_parts.append(f"""### Netflix
- **Visionnages :** {len(netflix):,}
- **Semaine binge record :** semaine {binge_week} ({binge_n} épisodes)
- **Top séries :** {', '.join(f"{s} ({n})" for s, n in top_shows.items()) or "n/a"}

""")

    if not tiktok.empty:
        night_tt = (tiktok["event_hour"].between(0, 5)).mean() * 100 if "event_hour" in tiktok.columns else 0
        md_parts.append(f"""### TikTok Watch
- **Vidéos regardées :** {len(tiktok):,}
- **Visionnage nocturne (0h–6h) :** {night_tt:.0f}%

""")

    if len(md_parts) == 1:
        md_parts.append("*Aucune donnée émotionnelle disponible.*\n")

    return "\n".join(md_parts), pd.DataFrame()



# ─── PACKAGE BUILDER ─────────────────────────────────────────────────────────

def build_package(start: str, end: str, sources: list, anon_names: bool, output_path: str):
    sections_md = []
    if "verbe" in sources:
        sections_md.append(build_verbe(start, end, anon_names)[0])
    if "inconscient" in sources:
        sections_md.append(build_inconscient(start, end)[0])
    if "emotionnel" in sources:
        sections_md.append(build_emotionnel(start, end)[0])

    dossier = f"""# Analyse Comportementale Numérique
*Généré le {datetime.now().strftime("%Y-%m-%d %H:%M")} | Période : {start} → {end}*
*Sources : {", ".join(sources)}*
{'*Anonymisation : prénoms remplacés par [PRÉNOM]*' if anon_names else ''}

> **Note :** Ce document est un outil de réflexion assistée, pas un diagnostic clinique.
> Il explore des tendances comportementales à partir de données numériques.
> Il ne remplace pas un professionnel de santé mentale.

---

{chr(10).join(sections_md)}
"""

    consigne = """# Consigne pour l'Analyste IA

## Rôle
Tu es un analyste comportemental neutre et bienveillant. Tu observes des patterns dans des données numériques, tu identifies des tendances et des contradictions, tu poses des questions ouvertes. Tu ne juges pas, tu ne moralises pas.

## Ce que tu N'es PAS
- Tu n'es pas un psychologue clinicien
- Tu ne poses pas de diagnostic
- Tu ne traites pas de troubles mentaux
- Tu ne gères pas de situations de crise

## Méthode
1. **Observation** : commence par une corrélation surprenante entre deux sources de données
2. **Tendances** : identifie 3-5 patterns comportementaux notables
3. **Contradictions** : relève les paradoxes entre ce qui est dit et ce qui est consommé/recherché
4. **Questions** : pose 2-3 questions ouvertes pour aider à la réflexion

## Style
- Calme, factuel, curieux
- Formulations d'hypothèses ("il semblerait que", "on observe une tendance à")
- Jamais d'affirmations définitives sur la personnalité

## Instruction d'amorce
Voici mon profil comportemental numérique sur la période indiquée.
Analyse les données et commence par une observation sur mes patterns ou évolutions.
"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("DOSSIER_COMPORTEMENTAL.md", dossier.encode("utf-8"))
        zf.writestr("CONSIGNE_ANALYSTE.md", consigne.encode("utf-8"))

        # Inclure les fichiers statiques du dossier data/Analyse comportementaliste/
        if os.path.isdir(STATIC_PACKAGE_DIR):
            for fname in os.listdir(STATIC_PACKAGE_DIR):
                fpath = os.path.join(STATIC_PACKAGE_DIR, fname)
                if os.path.isfile(fpath):
                    with open(fpath, "rb") as f:
                        zf.writestr(f"context/{fname}", f.read())

    return output_path
