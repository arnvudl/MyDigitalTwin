# MyDigitalTwin — Roadmap ML & Dashboard
_Mis à jour : 2026-04-15_

---

## Vue d'ensemble

```
src/scripts/
├── 01_exploration/          ✅ Ingestion + nettoyage Delta Lake
├── 02_clustering/           ✅ K-Means comportemental (6 profils) → /profils
├── 06_social/               ✅ Graphe social (Instagram) → /social
├── 04_clone/                ✅ Clone conversationnel (Gemini Flash) → /clone
├── 07_psy/                  ✅ Analyse Comportementale Numérique → /psy
├── 05_CLIP/                 ✅ Clustering photos CLIP (UMAP + HDBSCAN) → /photos
└── 03_als/                  🔜 Recommandations ALS → /recommandations + /netflix + /spotify
```

---

## Statut des axes

### ✅ AXE 0 — Ingestion & exploration
**Dossier** : `01_exploration/`

- Lecture de toutes les sources brutes (Google, YouTube, Spotify, Netflix, Instagram, TikTok, X…)
- Nettoyage, normalisation, écriture en Delta Lake / Parquet
- Warehouse : `google_searches`, `youtube_watch`, `spotify_streams`, `netflix_views`, `google_chrome`, `tiktok_watch`, `instagram_likes`, `twitter_tweets`

---

### ✅ AXE 3 — Clustering comportemental K-Means
**Dossier** : `02_clustering/`  

- K-Means comportemental : k=6, features temporelles + plateforme.
- Dashboard : page `/profils` (cards + filtres + exemples par cluster).

---

### ✅ AXE social — Graphe social Instagram
**Dossier** : `06_social/`

- Analyse des interactions (messages 1-to-1) et pondération.
- Dashboard : page `/social` (Cytoscape graph).

---

### ✅ AXE 1 — Clone conversationnel (V6 : Gemini Flash)
**Dossier** : `04_clone/`

**Pipeline** :
- `01_extract_corpus.py` — extraction + scoring des DMs Instagram → `dataset_final.jsonl`
- `02_build_gemini_corpus.py` — top 300 exemples → `gemini_corpus.txt`
- `app/pages/clone.py` — appel API Gemini Flash (system prompt + corpus injecté)

**⚠️ Limitation** : le corpus dépasse rapidement le free tier Gemini (250k tokens/min). Alternative : Groq (`llama-3.3-70b`) + réduire `TOP_N` à 50-100.

**Fine-tuning archivé** : `_outdated_03_finetune_runpod/` — voir `STATUS.md` pour l'historique V1-V3.

---

### ✅ AXE 5 — Analyse Comportementale Numérique
**Dossier** : `src/scripts/07_psy/`

- Wizard 4 étapes sur `/psy` : période, sources, anonymisation, génération
- ZIP généré : `Analyse_Comportementale_XXXX.zip`
  - `DOSSIER_COMPORTEMENTAL.md` : stats dynamiques (messages, recherches, Spotify, Amazon)
  - `CONSIGNE_ANALYSTE.md` : posture "Digital Twin Analyst" (neutre, pas de diagnostic)

---

### ✅ AXE 4 — Clustering photos CLIP
**Dossier** : `05_CLIP/`

- Embeddings CLIP ViT-L/14 (768 dims) + UMAP (cosine) + HDBSCAN
- 6 clusters + bruit — labels manuels après inspection visuelle
- Dashboard : page `/photos` — scatter UMAP 2D interactif + galerie par cluster

---

### 🔜 AXE 2 — Recommandations ALS *(prochaine étape)*
**Dossier** : `03_als/`

**Objectif** : donner un titre de film → score "Arnaud aimera à X%"

**Pipeline** :
1. `01_exploration/ingest_movielens.ipynb` *(à créer)* — MovieLens 32M CSV → Parquet warehouse
2. `01_build_interactions.ipynb` *(à mettre à jour)* — fusion MovieLens 32M + Netflix local
3. `02_als_model.ipynb` *(à mettre à jour)* — Spark ALS, top 50 reco
4. Bridge TMDB (tmdbId → affiches + résumés)

**Dashboard** : `/recommandations` + `/netflix`

**Voir** : `docs/nouvelle_als.md` + `src/scripts/03_als/PLAN.md`

---

## Dashboard — état des pages

| Page | Statut | Source |
|---|---|---|
| `/` Home | ✅ Live | Delta Lake (Global scoring) |
| `/profils` | ✅ Live | K-Means comportemental |
| `/social` | ✅ Live | Instagram graph |
| `/psy` | ✅ Live | Analyse Comportementale Numérique (ZIP) |
| `/clone` | ✅ Live | Gemini Flash + corpus DMs |
| `/photos` | ✅ Live | CLIP clusters (UMAP + HDBSCAN) |
| `/timeline` | ✅ Live | Vue agrégée (volume) |
| `/netflix` | 🔜 AXE 2 | ALS scores |
| `/recommandations` | 🔜 AXE 2 | ALS output + affiches TMDB |
