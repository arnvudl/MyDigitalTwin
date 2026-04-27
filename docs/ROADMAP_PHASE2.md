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
├── 2E  Dashboard — Performance & UX               ✅ FAIT (partiel)
├── 2F  Memory Album (Photos × Musique)
└── 2G  Topologie (Shape of Me)                    🔄 EN COURS
         ├── Infrastructure Docker + config         ✅ FAIT
         ├── Enrichissement (01_enrich.ipynb)       ✅ FAIT (TikTok: beh, IG: instaloader)
         ├── Dashboard page clusters.py             ✅ FAIT (topology_3d_template.html)
         ├── 02_islands.ipynb — pipeline complet    🔄 EN COURS (remplace 02_graph)
         └── Validation archipel + export JSON      ⬜ À faire
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
| `tiktok.ipynb` | `tiktok_watch`, `tiktok_likes`, `tiktok_searches` | ✅ (`tiktok_saves` à ajouter — Phase 2G) |
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

### Bonnes pratiques incrémentales — deux niveaux

#### Niveau 1 — Audit log ✅ FAIT (2026-04-27)

`data/ingestion_log.json` mis à jour automatiquement par `run_all.py` après chaque exécution.

```json
{
  "last_run": "2026-04-27T...",
  "sources": {
    "spotify":   { "last_run": "2026-04-27T...", "files_moved": 3 },
    "netflix":   { "last_run": "2026-04-27T...", "files_moved": 1 },
    "instagram": { "last_run": "2026-04-27T...", "files_moved": 0 }
  }
}
```

#### Niveau 2 — Delta MERGE INTO · après stabilisation des schémas

Remplacer l'approche actuelle (`read all → dropDuplicates → overwrite`) par un vrai upsert Delta.

```sql
-- Exemple Spotify
MERGE INTO warehouse.spotify_streams AS target
USING new_batch AS source
ON target.artistName = source.artistName
   AND target.trackName = source.trackName
   AND target.listen_ts  = source.listen_ts
WHEN NOT MATCHED THEN INSERT *
```

**Pourquoi attendre** : les schémas évoluent encore (Phase 2G va ajouter des tables). Refactoriser les MERGE avant que les schémas soient figés = refaire le travail deux fois.

- [ ] Définir les clés primaires par table (`ingestion_keys.md`)
- [ ] Migrer les notebooks vers `MERGE INTO` une fois Phase 2G terminée

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

## 2E — Dashboard : Performance & UX ✅ (partiel)

### Réalisé (2026-04-27)

- **Netflix** : réécriture complète — plus d'ALS, posters TMDB via `search/multi`
  - Cache TMDB persistant sur disque (`warehouse/tmdb_poster_cache.json`)
  - Fetch parallèle (`ThreadPoolExecutor(max_workers=10)`) — ~1.5s au lieu de ~14s
  - Bouton "Voir tout · N titres" par section (séries / films) — grille flex-wrap expandable
  - Section posters séparée en callback indépendant (ne se rechargne pas au changement de période)
- **Spotify** : `prefetch_artists()` / `prefetch_tracks()` parallèles, batch save (1 seule écriture disque)
- **ALS/recommandations** : suppression complète de `interaction_weight` dans tous les notebooks + `recommandations.py` supprimé

### Problème 1 — Chargement lent ✅ (résolu pour Netflix + Spotify)
- Cache `@lru_cache` sur les fonctions de chargement ✅
- Fetch API parallèle via `ThreadPoolExecutor` ✅
- Cache disque persistant pour TMDB et Spotify metadata ✅

### Problème 2 — HTML/CSS dans des strings Python
- Déjà partiellement fait (`social_3d.html`, `style.css`)
- Topology suivra le même pattern (standalone HTML + Dash wrapper)

### Navbar — Réorganisation "Wow vs Tech"

```
[ MyDigitalTwin ]   |  EXPLORE : Home · Timeline · Memory Album · Social · Clone
                    |  ANALYSE : Shape of Me · Netflix · Spotify · Psy · Inventaire
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

### Actions
- [ ] Script d'import photos iCloud + extraction EXIF (date, GPS)
- [ ] Clustering musical via Spotify Audio Features
- [ ] Mapping cluster photo (CLIP) ↔ cluster musical
- [ ] Page Dash "Memory Album"

---

## 2G — Topology Graph (Shape of Me) ✨ 🔄 EN COURS

### Vision
Créer un archipel d'îles 3D ("Vice-Versa" style) représentant les centres d'intérêts.
Chaque île est un amas sémantique et comportemental. Les items (tweets, vidéos, musiques)
sont placés en 3D selon leurs similarités, puis regroupés par HDBSCAN.
Les îles sont nommées automatiquement (TF-IDF / LLM) depuis leur contenu textuel.

---

### Évolution de la réflexion (2026-04-27)
1. **Clustering classique (`02_clustering/_outdated`)** : Trop rigide et basé uniquement sur le temps.
2. **TDA Mapper (`02_graph.ipynb`)** : Graphe mathématique puissant, mais complexe, abstrait et dur à calibrer (DBSCAN metric=precomputed issues). Moins lisible pour un utilisateur final.
3. **Archipel 3D (UMAP + HDBSCAN)** : Le choix final. UMAP 3D transforme la matrice hybride ($D_{final}$) en un "océan" où les comportements et sémantiques similaires forment des îles. HDBSCAN les détecte sans hyperparamètres complexes. Très visuel ("Vice-Versa").

---

### Architecture technique — Distance hybride et Îles 3D

La matrice de distance hybride $D_{final}$ est conservée, car elle permet de mixer parfaitement le sémantique et le comportemental.

```
D_final(i,j) = α · D_sem(i,j) + (1-α) · D_beh(i,j)     α ≈ 0.5
```
*(L'imputation contextuelle est conservée pour les données 100% comportementales comme TikTok ou les likes Insta)*

**Pipeline "Îles" :**
```
D_final (precomputed)
    ↓
UMAP 3D  (metric="precomputed", n_components=3)
    → Génère les coordonnées x, y, z dans "l'Océan"
    ↓
HDBSCAN  (sur l'espace 3D)
    → Détecte les îles (clusters denses) et le bruit (l'océan)
    ↓
TF-IDF   (sur les items AVEC texte de chaque île)
    → Nomme l'île (ex: "Dev Web, Python")
    ↓
Export JSON pour Plotly 3D ou 3d-force-graph (sans arêtes, juste les points/îles)
```

---

### Dashboard — Page "Shape of Me" (`/topology`)

**Visuel cible :**
- Nuage de points interactif 3D (Plotly 3D ou Three.js adapté).
- L'espace est vide, on voit de grands amas de points = les îles.
- Au centre des îles flotte un label (les mots-clés extraits).
- Clic sur un point = vue de l'item (tweet, vidéo).

**Fichiers :**
- `app/pages/clusters.py` → à adapter pour l'archipel
- `src/scripts/02_topology/02_islands.ipynb` → Remplacera `02_graph.ipynb`

---

## Historique des décisions techniques

### 2026-04-24 — Phase 1 terminée
Dashboard opérationnel. Notebooks exploration tous les sources.

### 2026-04-25 → 2026-04-27 — Nettoyage ALS complet
- Suppression de `interaction_weight` dans les 6 notebooks d'exploration
- `recommandations.py` supprimé (page ALS orpheline)
- `app/app.py` : `_load_recos()` retiré du prewarm
- `run_all.py` : audit log `ingestion_log.json` ajouté

### 2026-04-27 — Netflix & Spotify performance
- Netflix : cache TMDB disque + fetch parallèle + "Voir tout" expandable
- Spotify : prefetch parallèle + batch save
- Suppression ALS → TMDB poster grid sans recommandations

### 2026-04-27 — Décision : TDA Mapper archivé, passage à l'Archipel 3D
TDA Mapper posait des problèmes de calibration et la notion de "graphe" s'avérait moins lisible pour l'utilisateur qu'une simple "carte d'îles" façon *Vice-Versa*.
La matrice de distance hybride ($D_{final}$) et le système d'imputation contextuelle sont excellents et sont conservés.
Nouveau pipeline : UMAP 3D sur $D_{final}$ → HDBSCAN → Extraction de mots-clés (TF-IDF).
Le script `02_graph.ipynb` sera remplacé par `02_islands.ipynb`.

---

## Priorités

| Priorité | Tâche | Statut |
|---|---|---|
| ✅ FAIT | Nettoyage ALS complet (tous notebooks + pages) | Fait |
| ✅ FAIT | Netflix : TMDB poster grid + cache disque + fetch parallèle | Fait |
| ✅ FAIT | Spotify : prefetch parallèle + batch save | Fait |
| ✅ FAIT | `01_enrich.ipynb` — TikTok (0%→beh) + Instagram bios | Fait |
| ✅ FAIT | Docker : `config.yaml` monté, `instaloader` volume, consolidé | Fait |
| 🔴 NEXT | **Remplacer `02_graph.ipynb` par `02_islands.ipynb` (UMAP 3D + HDBSCAN)** | À faire |
| 🔴 NEXT | **Page Dash "Shape of Me" : Plotly 3D Archipel** | À faire |
| 🟠 P1 | R2 cloud storage | À faire |
| 🟡 P2 | Delta `MERGE INTO` par table (niveau 2, post-stabilisation schémas) | Après Phase 2G |
| 🟡 P2 | Unit tests + GitHub Actions CI | À faire |
| 🟡 P2 | Memory Album (clustering musique + UI) | À faire |
| 🟢 P3 | Navbar réorganisation (Shape of Me · Explore / Analyse) | Après Phase 2G |
| 🔵 P4 | Copier template | À faire |
| 🔵 P4 | LangSmith pour le clone | À faire |

---

*Roadmap rédigée le 2026-04-24 — mise à jour le 2026-04-27 (Passage de TDA Mapper à Archipel 3D).*