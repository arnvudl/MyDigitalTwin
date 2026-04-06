# MyDigitalTwin — Roadmap ML & Dashboard
_Mis à jour : 2026-04-06_

---

## Vue d'ensemble

```
src/scripts/
├── 01_exploration/          ✅ Ingestion + nettoyage Delta Lake
├── 02_clustering/           ✅ K-Means comportemental (6 profils) → /profils
├── 03_als/                  🔜 Recommandations ALS → /recommandations + /netflix + /spotify
├── 04_clone/                🔜 Clone conversationnel RAG → /clone
└── 05_CLIP/                 ⏳ Clustering photos CLIP → /photos  (après 10 mai)
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
**Terminé** : 2026-04-06

- Analyse fréquentielle par source (remplace TF-IDF K-Means trop hétérogène)
- K-Means comportemental : k=6, features temporelles + plateforme, Silhouette 0.32
- Outputs : `warehouse/behavioral_clusters`, `warehouse/interest_profiles`
- Dashboard : page `/profils` (cards + filtres + exemples par cluster)
- Home page : enrichissement `CATEGORY_KEYWORDS` avec données Delta (keywords data-driven)

---

### 🔜 AXE 2 — Recommandations ALS *(priorité haute)*
**Dossier** : `03_als/`  
**Voir** : `03_als/PLAN.md`

**Objectif** : donner un titre → score "Arnaud aimera à X%"

- ALS implicite sur interactions Spotify + Netflix + YouTube
- Unification en `warehouse/interactions.parquet`
- Dashboard : `/recommandations` (score + top suggestions) + `/netflix` + `/spotify` (Wrapped custom)

**Pourquoi en premier** : données déjà propres dans le warehouse, pipeline le plus direct.

---

### 🔜 AXE 1 — Clone conversationnel RAG *(priorité moyenne)*
**Dossier** : `04_clone/`  
**Voir** : `04_clone/PLAN.md`

**Objectif** : chatbot qui parle comme Arnaud

**Approche** : RAG-style (pas de fine-tuning — 8 Go VRAM insuffisants)
- Corpus : tweets + commentaires Instagram + DMs sélectionnés manuellement
- NLP PySpark : n-grams, emojis, profil de style
- Index vectoriel (FAISS/ChromaDB) + prompt enrichi → Claude API ou Mistral local (Ollama)
- Dashboard : `/clone`

**Pré-requis** : sélection manuelle des DMs intéressants par Arnaud.

---

### ⏳ AXE 4 — Clustering photos CLIP *(après 10 mai)*
**Dossier** : `05_CLIP/`  
**Voir** : `05_CLIP/PLAN.md`

**Objectif** : grouper les photos Instagram par thème (soirées, concerts, voyages…)

- CLIP `openai/clip-vit-large-patch14` → embeddings 768 dims
- K-Means PySpark sur embeddings → clusters thématiques
- Labelling automatique via CLIP text similarity
- Dashboard : `/photos`

---

## Dashboard — état des pages

| Page | Statut | Source |
|---|---|---|
| `/` Home | ✅ Live | Delta Lake (keywords + scoring) |
| `/profils` | ✅ Live | `behavioral_clusters` + `interest_profiles` |
| `/netflix` | 🔜 AXE 2 | `netflix_views` + ALS scores |
| `/spotify` | 🔜 AXE 2 | `spotify_streams` + Wrapped custom |
| `/recommandations` | 🔜 AXE 2 | ALS output |
| `/clone` | 🔜 AXE 1 | Corpus texte + RAG |
| `/timeline` | ⏳ À évaluer | Tous les parquets (volume à tester) |
| `/social` | ⏳ À faire | Instagram follows + DMs + TikTok messages |
| `/photos` | ⏳ Après 10 mai | CLIP embeddings + photo clusters |

---

## Graphe social — note

**Page `/social`** : graphe de tes relations sociales.
- Nœuds : personnes que tu suis **et** qui te suivent (mutual follows Instagram)
- Arêtes : épaisseur proportionnelle au volume de messages (DMs Instagram + TikTok)
- Données : `instagram_follows.json` + messages inbox
- Affichage : nom + photo de profil si disponible (données Instagram export)
- Librairie suggérée : `dash-cytoscape` ou `pyvis`

---

## Ordre d'exécution recommandé

```
1. 03_als/  →  /netflix + /spotify + /recommandations   (données prêtes)
2. 04_clone/  →  /clone                                  (nécessite sélection DMs)
3. /social                                               (données Instagram)
4. /timeline                                             (évaluer volume d'abord)
5. 05_CLIP/  →  /photos                                  (après 10 mai)
```
