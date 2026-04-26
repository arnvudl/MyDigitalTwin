# MyDigitalTwin — Roadmap Phase 2 : Data Engineering

> **Contexte** : Le PoC (Phase 1) est terminé. Le dashboard tourne, les notebooks explorent les données Spotify, Instagram, Netflix, YouTube, TikTok, Twitter, Google. Phase 2 = industrialiser, pérenniser, enrichir.

---

## Vue d'ensemble

```
Phase 2
├── 2A  Infrastructure & Stockage cloud
├── 2B  Ingestion & Stratégie de stockage          ✅ FAIT
├── 2C  Qualité du code & Reproductibilité
├── 2D  Tests & CI
├── 2E  Dashboard — Performance & UX
├── 2F  Memory Album (Photos × Musique)
└── 2G  Topologie (Shape of Me)                    🔄 EN COURS
```

---

## 2A — Infrastructure & Stockage cloud

### Objectif
Sortir le warehouse du PC local vers un stockage objet S3-compatible, gratuit.

### Choix retenu : **Cloudflare R2**
| Critère | R2 | Backblaze B2 |
|---|---|---|
| Free tier | 10 GB stockage, 0 frais de sortie | 10 GB stockage, 1 GB/jour sortie |
| API S3 | Oui | Oui |
| Latence EU | Bonne | Bonne |
| **Verdict** | ✅ Meilleur (pas de frais egress) | Alternative |

### Architecture cible
```
data/processed/    ← exports GDPR normalisés (gitignored, permanents)
    ↓ notebooks Spark
R2 Bucket
├── processed/     ← données brutes archivées (immutables)
├── warehouse/     ← Delta Lake tables (lecture par Spark/pandas)
└── models/        ← embeddings CLIP, modèle ALS
```

### Actions
- [ ] Créer compte Cloudflare + bucket R2
- [ ] Configurer `config.py` avec `R2_ENDPOINT`, `R2_BUCKET` (via `.env`)
- [ ] Adapter `WAREHOUSE` dans `config.py` pour pointer vers R2 (protocol `s3a://`)
- [ ] Tester lecture/écriture Spark → R2 via `hadoop-aws` + clés d'accès

---

## 2B — Ingestion & Stratégie de stockage ✅

### Architecture actuelle (opérationnelle)

```
data/
├── inbox/       ← zone de transit — fichiers GDPR bruts déposés ici
│                   → déplacés automatiquement dans processed/ par les parsers
└── processed/   ← données normalisées, permanentes (gitignored)
    ├── INSTAGRAM/
    ├── GOOGLE/
    ├── TIKTOK/
    ├── TWITTER/   (processed/X/)
    ├── SPOTIFY/
    │   ├── account/   ← StreamingHistory_music_*.json, YourLibrary.json, ...
    │   └── extended/  ← Streaming_History_Audio_*.json (depuis 2020)
    └── NETFLIX/
```

**Flux d'ingestion :**
1. Décompresser/déposer l'export dans `data/inbox/`
2. `python -m src.ingestion.run_all` (ou `--sources spotify netflix`)
3. Parser détecte le dossier/fichier, le déplace dans `processed/<SOURCE>/`
4. Relancer le notebook correspondant dans Docker

### Parsers implémentés (`src/ingestion/`)

| Parser | OVERWRITE | Stratégie |
|---|---|---|
| `instagram.py` | False | Incrémental — accumule les exports |
| `google.py` | False | Incrémental — accumule les Takeouts |
| `tiktok.py` | True | Full — export monolithique |
| `twitter.py` | True | Full — export monolithique |
| `spotify.py` | False | Incrémental — account/ et extended/ séparés |
| `netflix.py` | True | Full — CSV complet à chaque export |

### Stratégie incrémentale Spotify ✅

Extended History couvre 2020 → 2025-05-03. Account Data couvre 2025-03 → 2026-03.
- Union des deux sources → déduplication par `(artistName, trackName, minute)` en favorisant Extended (schéma riche)
- Écriture Delta `overwrite` — idempotent
- Au prochain export : nouveaux fichiers s'accumulent dans `processed/` (OVERWRITE=False), relancer le notebook suffit

### Notebooks warehouse — état

| Notebook | Table(s) écrite(s) | Statut |
|---|---|---|
| `spotify.ipynb` | `spotify_streams`, `spotify_liked_songs`, `spotify_playlists`, `spotify_searches` | ✅ Mis à jour (Extended+Account, dedup) |
| `netflix.ipynb` | `netflix_views` | ✅ Prêt (CSV dans processed/NETFLIX/) |
| `instagram.ipynb` | `instagram_likes`, `instagram_saved`, `instagram_comments`, `instagram_posts_viewed`, `instagram_videos_watched`, `instagram_story_likes`, `instagram_searches` | ✅ |
| `google_youtube.ipynb` | `google_searches`, `google_chrome`, `youtube_watch` | ✅ |
| `tiktok.ipynb` | `tiktok_watch`, `tiktok_likes`, `tiktok_saves`, `tiktok_searches` | ✅ (tiktok_saves ajouté) |
| `twitter.ipynb` | `twitter_tweets`, `twitter_likes` | ✅ |

### Sources GDPR — état

| Source | Parser | Données dans processed/ |
|---|---|---|
| Instagram | ✅ | ✅ |
| Google / YouTube | ✅ | ✅ |
| TikTok | ✅ | ✅ |
| Twitter/X | ✅ | ✅ |
| Spotify | ✅ | ✅ (account/ + extended/) |
| Netflix | ✅ | ✅ |

---

## 2C — Reproductibilité & Structure du repo

### Objectif
N'importe qui fait `git clone` + remplit son `.env` et ça marche.

### Structure cible (conventions data engineering)

```
MyDigitalTwin/
├── .env.example          ← template de secrets (jamais .env dans git)
├── config.py             ← ✅ déjà là, à enrichir
├── Makefile              ← ✅ déjà là
├── docker-compose.yml    ← ✅ déjà là
├── requirements.txt      ← à versionner précisément (pin versions)
│
├── data/
│   ├── inbox/            ← zone de transit (gitignored)
│   ├── processed/        ← exports GDPR normalisés (gitignored)
│   └── warehouse/        ← local fallback si pas de R2 (gitignored)
│
├── src/
│   ├── ingestion/        ← ✅ parsers implémentés
│   ├── scripts/          ← ✅ notebooks d'exploration
│   └── utils/            ← fonctions partagées entre notebooks
│
├── app/                  ← ✅ dashboard Dash
├── tests/                ← unit tests + data quality (à faire)
├── docs/
│   ├── rapport/
│   └── ROADMAP_PHASE2.md ← ce fichier
└── CLAUDE.md
```

### Reproductibilité : Docker (standard) + venv (fallback)
- Docker = reproductible partout sans installer Python/Java/Spark → **standard**
- venv + `requirements.txt` pinnés = pour ceux qui veulent juste le dashboard sans Spark
- `Makefile` comme point d'entrée unique : `make setup`, `make ingest`, `make dashboard`

### Templating : **Copier**
- `copier copy gh:ton-repo` génère la structure + `.env.example` pré-rempli
- L'utilisateur remplit `config.py` (ses amis Instagram, ses artistes Spotify)
- **Copier > Cookiecutter** : `copier update` permet aux projets dérivés de récupérer les améliorations
- GitHub Template = alternative simple mais sans personnalisation ni mise à jour

---

## 2D — Tests & CI

### Stratégie retenue : 2 niveaux

#### 1. Unit Tests (`tests/unit/`)
```
tests/unit/
├── test_spotify_parser.py
├── test_instagram_parser.py
└── test_config.py
```

#### 2. Data Quality Tests (`tests/data_quality/`)
```python
assert df["ts"].notna().all(), "Timestamps manquants dans Spotify"
assert df["track_name"].nunique() > 100, "Trop peu de tracks"
```

#### CI — GitHub Actions
- Déclenché sur chaque PR : lint (ruff) + unit tests
- Pas de tests data quality en CI (données privées non commitées)

### Outils MLOps — ce qui est utile ici

| Outil | Verdict |
|---|---|
| **DVC** | ⚠️ Utile pour versionner les exports GDPR — pas prioritaire |
| **MLflow** | ❌ Pas pertinent — on n'entraîne pas de modèles custom |
| **LangSmith** | ✅ Utile pour la partie LLM (Clone) — Phase 3 |
| **Kedro** | ✅ Oui — mais gros chantier. Phase 3 uniquement |

---

## 2E — Dashboard : Performance & UX

### Problème 1 — Chargement lent
- Lazy loading : ne charger les données qu'au premier accès (callbacks au lieu de layout statique)
- Cache `@lru_cache` sur les fonctions de chargement (déjà fait sur `_load_spotify()`)
- Pré-agréger les données dans des fichiers légers au moment de l'ingestion

### Problème 2 — HTML/CSS dans des strings Python
- Tout HTML → `app/assets/*.html` chargé via `open()`
- Tout CSS → `app/assets/*.css` (Dash charge automatiquement)
- Déjà partiellement fait (`social_3d.html`, `style.css`)

### Navbar — Réorganisation "Wow vs Tech"

```
[ MyDigitalTwin ]   |  EXPLORE : Home · Timeline · Memory Album · Social · Clone
                    |  ANALYSE : Profils · Netflix · Spotify · Psy · Inventaire
```

---

## 2F — Memory Album (Photos × Musique) ✨

### Vision
Album photo interactif où chaque moment est associé à une ambiance musicale.

### Approche technique

```
Photos  ──CLIP embeddings──► clusters visuels (festif, nature, intime, voyage)
Musiques ──Spotify Audio Features──► clusters musicaux (énergique, mélancolique)
    (valence, energy, danceability, tempo — Spotify API officielle)
                    │
              Mapping cluster photo → cluster musical
```

**Association temporelle** : si une photo date du 14/06/2024 et que Spotify montre une
écoute intense ce soir-là → lier directement. Sinon, fallback sur le cluster émotionnel.

### Actions
- [ ] Script d'import photos iCloud + extraction EXIF (date, GPS)
- [ ] Clustering musical via Spotify Audio Features
- [ ] Mapping cluster photo (CLIP) ↔ cluster musical
- [ ] Page Dash "Memory Album"

---

## 2G — Topology Graph (Shape of Me) ✨ 🔄 EN COURS

### Vision
Graphe de connaissances 3D — contenus likés/sauvegardés cross-plateformes,
spatialisés sémantiquement via embeddings + TDA. Chaque nœud = un contenu aimé.
La forme révèle les clusters d'intérêt réels, sans keyword matching.

---

### Étape 1 — Données warehouse

| Table | Champ texte | URL | Statut |
|-------|-------------|-----|--------|
| `instagram_likes` | — | `post_url` | ✅ warehouse |
| `instagram_saved` | `account` | `post_href` | ✅ warehouse |
| `twitter_likes` | `full_text` | reconstruit depuis `tweet_id` | ✅ warehouse |
| `tiktok_likes` | `video_desc` | `video_url` | ✅ warehouse |
| `tiktok_saves` | `video_desc` | `video_url` | ✅ warehouse |
| `spotify_liked_songs` | `track + artist` | `trackUri` | ✅ warehouse |

**Toutes les tables sources sont prêtes.** ✅

---

### Étape 2 — Notebook topologie

**Fichier :** `src/scripts/04_topology/01_topology_graph.ipynb`

```
Tables warehouse
├── instagram_likes / instagram_saved
├── twitter_likes
├── tiktok_likes / tiktok_saves
└── spotify_liked_songs
         │
         ▼
DataFrame unifié : (id, url, text, platform, action_type)
         │
         ▼
Embedding texte  →  all-MiniLM-L6-v2  →  vecteurs 384D
         │
         ├── PCA 3D        →  x_pca,  y_pca,  z_pca
         ├── UMAP 3D       →  x_umap, y_umap, z_umap   (Centroid mode)
         └── Hiérarchique  →  structure arbre            (H3 Tree mode)
         │
         ▼
TDA Mapper (KeplerMapper)  →  clusters + arêtes
         │
         ▼
warehouse/topology_nodes   (id, url, platform, label, coords, cluster_id)
warehouse/topology_edges   (source, target, weight)
```

- [ ] Notebook `01_topology_graph.ipynb`
- [ ] `pip install keplerMapper sentence-transformers umap-learn` → `requirements/ml.txt`

---

### Étape 3 — Page app

**Fichiers :** `app/pages/topology.py` + `app/assets/topology/graph.html`

#### Stack technique
- Page HTML standalone dans `app/assets/topology/` — Three.js + `3d-force-graph`
- Données injectées au build : warehouse → `app/assets/topology/data.json`
- Intégrée dans Dash via `html.Iframe` plein écran

#### Rendu visuel
- Fond `#000000` — esthétique hologramme spatial
- **Nœuds** : sphères colorées par plateforme + label blanc flottant
- **Arêtes** : `rgba(255,255,255,0.08)` — très fines, translucides, constellation

#### Couleurs plateformes
| Plateforme | Couleur |
|------------|---------|
| Instagram | `#E1306C` |
| Twitter/X | `#1DA1F2` |
| TikTok | `#69C9D0` |
| Spotify | `#1DB954` |

#### Modes de layout
| Mode | Algorithme | Esthétique |
|------|-----------|------------|
| **Force** | Force-directed 3D | Réseau neuronal, organique |
| **PCA** | Coordonnées PCA3D | Galaxie plate |
| **Centroid** | Distance au centroïde | Amas globulaire |

#### Interaction clic
- Orbite / zoom : clic + drag souris
- Clic nœud → panneau latéral avec iframe embed officiel
- Iframe selon la plateforme : Tweet, Instagram, TikTok, Spotify embed

#### Actions
- [ ] `app/assets/topology/graph.html` — Three.js + 3d-force-graph + 3 modes
- [ ] `app/assets/topology/data.json` — export depuis le notebook
- [ ] `app/pages/topology.py` — Dash wrapper (iframe + panneau latéral)
- [ ] Ajouter "Topology" dans la navbar

---

### Ordre d'exécution restant

```
1. ✅ tiktok_saves       → warehouse
2. ✅ spotify_liked_songs → warehouse
3. Notebook topologie   → topology_nodes + topology_edges  ← PROCHAIN
4. graph.html           → Three.js + 3d-force-graph
5. topology.py          → Dash wrapper
```

---

## Horizon inspirationnel — NeuroAI

Ce projet touche à des thèmes au cœur du NeuroAI : représentation de la mémoire épisodique,
association multimodale (visuel + auditif), reconstruction de souvenirs par l'émotion.

Pistes à explorer :
- Groupes : DeepMind (Neuroscience team), Meta AI (FAIR), Mila (Montréal), INRIA
- Mots-clés : *episodic memory*, *multimodal memory consolidation*, *affective computing*
- Stages : ce projet illustre exactement ces problèmes — bon portfolio concret

---

## Priorités

| Priorité | Tâche | Statut |
|---|---|---|
| ✅ FAIT | Parsers tous les sources (inbox → processed/) | Fait |
| ✅ FAIT | Ingestion incrémentale Spotify (Extended + Account, dedup) | Fait |
| ✅ FAIT | `tiktok_saves`, `spotify_liked_songs`, `spotify_searches` | Fait |
| ✅ FAIT | Fix paths app (`data/raw/` → `data/processed/`) | Fait |
| ✅ FAIT | Fix `sys.path` notebooks (walk-up config.py) | Fait |
| 🔴 NEXT | Notebook topologie `04_topology/01_topology_graph.ipynb` | À faire |
| 🔴 NEXT | `graph.html` + `topology.py` (Phase 2G app) | À faire |
| 🟠 P1 | R2 cloud storage | À faire |
| 🟡 P2 | Unit tests + GitHub Actions CI | À faire |
| 🟡 P2 | Memory Album (clustering musique + UI) | À faire |
| 🟢 P3 | Navbar réorganisation (Explore / Analyse) | À faire |
| 🔵 P4 | Copier template | À faire |
| 🔵 P4 | LangSmith pour le clone | À faire |

---

*Roadmap rédigée le 2026-04-24 — mise à jour le 2026-04-26 (ingestion complète, topology data ready).*
