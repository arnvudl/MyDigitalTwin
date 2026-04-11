# MyDigitalTwin — Roadmap ML & Dashboard
_Mis à jour : 2026-04-10_

---

## Vue d'ensemble

```
src/scripts/
├── 01_exploration/          ✅ Ingestion + nettoyage Delta Lake
├── 02_clustering/           ✅ K-Means comportemental (6 profils) → /profils
├── 06_social/               ✅ Graphe social (Instagram) → /social
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

### ✅ AXE social — Graphe social Instagram
**Dossier** : `06_social/`
**Terminé** : 2026-04-10

- Analyse des interactions (messages 1-to-1)
- Pondération par volume de messages et statut "Close Friends"
- Visualisation interactive du réseau de relations
- Dashboard : page `/social` (Cytoscape graph)

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

### 🔜 AXE 1 — Clone conversationnel (Fine-tuning Cloud) *(priorité moyenne)*
**Dossier** : `04_clone/`  
**Voir** : `docs/clone_finetuning.md`

**Objectif** : un modèle (Llama 3 / Mistral) qui parle nativement comme Arnaud.

**Approche** : Fine-tuning externe (RunPod / Vast.ai)
- **Pré-traitement Hyper-Quali** : sélection manuelle et nettoyage drastique des DMs (500-1000 paires instruction/réponse).
- **Entraînement** : Utilisation de QLoRA (Unsloth/Axolotl) sur GPU cloud (RTX 3090/4090).
- **Export** : Modèle quantifié GGUF pour usage local via Ollama.
- **Dashboard** : Page `/clone` connectée à l'API locale.

**Pré-requis** : préparation manuelle du dataset JSONL par Arnaud (travail sur la qualité > quantité).

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
| `/social` | ✅ Live | Instagram follows + DMs + Cytoscape |
| `/netflix` | 🔜 AXE 2 | `netflix_views` + ALS scores |
| `/spotify` | 🔜 AXE 2 | `spotify_streams` + Wrapped custom |
| `/recommandations` | 🔜 AXE 2 | ALS output |
| `/clone` | 🔜 AXE 1 | Corpus texte + RAG |
| `/timeline` | ✅ Live | Vue agrégée de tous les événements (volume OK) |
| `/photos` | ⏳ Après 10 mai | CLIP embeddings + photo clusters |

---

## 📊 Timeline des données (Warehouse)

*Analyse automatique du contenu du warehouse pour l'axe `/timeline`.*

| Source | Volume | Période couverte | État |
|---|---|---|---|
| **TikTok** | 234 771 vues | 2024-03 → 2026-04 | ✅ Riche |
| **Google Searches** | 55 854 recherches | 2018-01 → 2026-04 | ✅ Historique long |
| **Spotify** | 33 972 streams | 2025-03 → 2026-03 | ✅ Actif |
| **Instagram** | 17 535 likes | 2015-06 → 2026-04 | ✅ Très ancien |
| **YouTube** | 13 821 vues | 2018-05 → 2026-04 | ✅ Stable |
| **Netflix** | 4 288 sessions | 2017-10 → 2026-04 | ✅ Complet |
| **Twitter** | 319 tweets | 2019-06 → 2026-03 | ⚠️ Faible volume |

---

## Ordre d'exécution recommandé

```
1. 03_als/  →  /netflix + /spotify + /recommandations   (données prêtes)
2. 04_clone/  →  /clone                                  (nécessite sélection DMs)
3. 05_CLIP/  →  /photos                                  (après 10 mai)
```
