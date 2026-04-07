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

## Graphe social — architecture détaillée

**Page `/social`** : réseau de relations basé sur les conversations privées.

### Logique de construction

1. **Parsing de l'inbox** (`data/raw/INSTAGRAM/your_instagram_activity/messages/inbox/`)
   - Chaque dossier = conversation (1-to-1 ou groupe)
   - **Identifier 1-to-1** : vérifier dans le JSON si seulement 2 participants ("A R N A U D" + 1 autre)
   - **Ignorer les groupes** : ne garder que les conversations privées
   - Extraire pseudo du nom du dossier (ex: `3li0tttt_17939266904472883` → `3li0tttt`)

2. **Comptage des messages**
   - Lire le fichier `message_*.json` avec le plus grand numéro (ex: `message_2.json` > `message_1.json`)
   - Compter le nombre de messages total dans ce fichier
   - En cas d'égalité de messages entre deux personnes : utiliser le compte pour départager

3. **Pondération des nœuds**
   - Vérifier si pseudo ∈ `close_friends.json` : multiplicateur de poids (ajustable, ex: 2x)
   - Vérifier si pseudo ∈ `followers_1.json` : poids normal
   - **Personnes hors listes : exclure**
   - **Avant le calcul** : possibilité d'ajuster la liste `close_friends` manuellement

4. **Construction du graphe**
   - Nœuds : pseudos des personnes (poids = nombre de messages × multiplicateur close_friends)
   - Arêtes : lien vers Arnaud, épaisseur ∝ poids du nœud
   - Visualisation : `dash-cytoscape` ou `pyvis` avec layout force-directed

5. **Enrichissement visuel** (optionnel)
   - Photos de profil via API Instagram (nécessite token)
   - Fallback : redirection vers profil Instagram, ou affichage du pseudo en couleur

### Données source
- `data/raw/INSTAGRAM/connections/followers_and_following/close_friends.json`
- `data/raw/INSTAGRAM/connections/followers_and_following/followers_1.json`
- `data/raw/INSTAGRAM/your_instagram_activity/messages/inbox/*/message_*.json`

### Étapes d'implémentation
1. Parser inbox + identifier 1-to-1
2. Compter messages et construire DataFrame `(pseudo, message_count, in_close_friends)`
3. Appliquer poids + visualiser graphe statique
4. Dashboard interactif (filtres, détails au hover)
5. API Instagram pour photos (si temps)

---

## Ordre d'exécution recommandé

```
1. 03_als/  →  /netflix + /spotify + /recommandations   (données prêtes)
2. 04_clone/  →  /clone                                  (nécessite sélection DMs)
3. /social                                               (données Instagram)
4. /timeline                                             (évaluer volume d'abord)
5. 05_CLIP/  →  /photos                                  (après 10 mai)
```
