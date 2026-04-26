# MyDigitalTwin — Roadmap Phase 2 : Data Engineering

> **Contexte** : Le PoC (Phase 1) est terminé. Le dashboard tourne, les notebooks explorent les données Spotify, Instagram, Netflix, YouTube, TikTok, Twitter, Google. Phase 2 = industrialiser, pérenniser, enrichir.

---

## Vue d'ensemble

```
Phase 2
├── 2A  Infrastructure & Stockage cloud
├── 2B  Ingestion & Stratégie de stockage
├── 2C  Qualité du code & Reproductibilité
├── 2D  Tests & CI
├── 2E  Dashboard — Performance & UX
├── 2F  Memory Album (Photos × Musique)
└── 2G  Topologie (Shape of Me)
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
data/raw/          ← export GDPR local (gitignored, temporaire)
    ↓ ingestion
R2 Bucket
├── raw/           ← données brutes archivées (immutables)
├── warehouse/     ← Delta Lake tables (lecture par Spark/pandas)
└── models/        ← embeddings CLIP, modèle ALS
```

### Actions
- [ ] Créer compte Cloudflare + bucket R2
- [ ] Configurer `config.py` avec `R2_ENDPOINT`, `R2_BUCKET` (via `.env`)
- [ ] Adapter `WAREHOUSE` dans `config.py` pour pointer vers R2 (protocol `s3a://`)
- [ ] Tester lecture/écriture Spark → R2 via `hadoop-aws` + clés d'accès

---

## 2B — Ingestion & Stratégie de stockage

### Stratégie pendant la phase de développement

**Principe : écrasement complet (overwrite-only)**

Tant que le schéma des parquets évolue, les parsers changent et les transformations ne sont pas stables → on ne cherche pas à merger de façon incrémentale. Chaque ingestion réécrit entièrement les parquets concernés.

```
data/
├── inbox/      ← zone de transit — fichiers reçus (GDPR exports décompressés)
│                  → déplacés dans raw/ puis supprimés de inbox/
├── raw/        ← ⚠️ TEMPORAIRE (dev uniquement) — archive locale brute
│                  → sera remplacé par R2 cloud en production
└── warehouse/  ← parquets générés (gitignored, toujours regénérables)
                   → écrasés intégralement à chaque ingestion
```

**Flux d'ingestion (dev) :**
1. Décompresser/déposer l'export dans `data/inbox/`
2. Parser déplace le contenu vers `data/raw/<SOURCE>/` (conservation temporaire locale)
3. Parser lit `data/raw/<SOURCE>/` et écrit/écrase `data/warehouse/<table>.parquet`
4. `data/inbox/` est vidé après traitement

> ⚠️ **`data/raw/` est temporaire** — ce dossier existe uniquement pendant la phase de développement pour conserver les exports GDPR localement sans stockage cloud. Il sera supprimé et remplacé par le bucket R2 (`raw/` distant) une fois la phase 2A déployée.

### Migration vers R2 (cible post-dev)

Quand `data/raw/` est remplacé par R2, **rien ne change dans les parsers** — c'est l'objectif de design :

```python
# Aujourd'hui (dev) :
RAW_ROOT = Path("data/raw")          # local

# Demain (prod) :
RAW_ROOT = "s3a://my-bucket/raw"     # R2 via s3a://
```

La classe `IngestorBase` abstrait ce chemin via `config.py`. Passer en prod = changer une variable d'environnement, pas réécrire les parsers.

**Checklist de migration :**
- [ ] Créer bucket R2 + configurer `R2_ENDPOINT`, `R2_BUCKET` dans `.env`
- [ ] Mettre `RAW_ROOT = s3a://...` dans `config.py` (conditionnel sur env `STORAGE_BACKEND`)
- [ ] Upload `data/raw/` → R2 via `rclone` ou `aws s3 cp`
- [ ] Supprimer `data/raw/` local
- [ ] Vérifier que les parsers lisent/écrivent correctement depuis R2

> L'ingestion incrémentale (merge dedup) sera également activée à ce moment : Delta Lake `MERGE INTO` une fois les schémas figés.

### Sources GDPR reçues (2026-04-25)

| Source | Statut | Fréquence future |
|---|---|---|
| **Instagram** | ✅ Reçu — dans `data/inbox/` | Mensuelle |
| **Google** | ✅ Reçu — dans `data/inbox/` | Trimestrielle |
| **TikTok** | ✅ Reçu — dans `data/inbox/` | Trimestrielle |
| **Spotify** | API officielle (déjà connectée) | Hebdomadaire (automatisable) |
| **Netflix** | GDPR export → email | Trimestrielle |
| **YouTube** | Google Takeout (dans export Google) | Trimestrielle |
| **Twitter/X** | GDPR export → email | Trimestrielle |
| **Apple / iCloud** | privacy.apple.com → email | Semestrielle (photos) |

### Parsers à implémenter (`src/ingestion/`)

```
src/ingestion/
├── __init__.py
├── base.py              ← IngestorBase (move inbox → raw, overwrite warehouse)
└── parsers/
    ├── __init__.py
    ├── instagram.py     ← messages, likes, followers
    ├── google.py        ← search history, location, YouTube watch
    └── tiktok.py        ← watch history, likes
```

### GDPR Reminders
Les plateformes envoient les données par email → les rappels sont gérés directement sur le téléphone (calendrier). Chaque ingestion logge la date dans `data/ingestion_log.json`.

```json
{
  "spotify": {"last_run": "2026-04-20", "rows_added": 142},
  "instagram": {"last_run": "2026-04-25", "rows_added": 0}
}
```

### Actions
- [ ] Créer `src/ingestion/base.py` (classe `IngestorBase`)
- [ ] Parser Instagram (`messages`, `liked_posts`, `followers`)
- [ ] Parser Google (`search_history`, `youtube_watch_history`)
- [ ] Parser TikTok (`watch_history`, `liked_videos`)
- [ ] Mettre à jour `ingestion_log.json` après chaque run

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
│   ├── raw/              ← exports GDPR locaux (gitignored)
│   └── warehouse/        ← local fallback si pas de R2 (gitignored)
│
├── src/
│   ├── ingest/           ← 🆕 modules d'ingestion par source
│   ├── scripts/          ← notebooks d'exploration (déjà là)
│   └── utils/            ← fonctions partagées entre notebooks
│
├── app/                  ← dashboard Dash (déjà là)
├── tests/                ← 🆕 unit tests + data quality
├── docs/
│   ├── rapport/          ← ✅ déjà là
│   └── ROADMAP_PHASE2.md ← ce fichier
└── CLAUDE.md
```

### Reproductibilité : Docker (standard) + venv (fallback)
- Docker = reproductible partout sans installer Python/Java/Spark → **standard**
- venv + `requirements.txt` pinnés = pour ceux qui veulent juste le dashboard sans Spark
- `Makefile` comme point d'entrée unique : `make setup`, `make ingest`, `make dashboard`

### Templating : **Copier**
Pour qu'un autre utilisateur puisse bootstrapper son propre MyDigitalTwin :
- `copier copy gh:ton-repo` génère la structure + `.env.example` pré-rempli avec quelques questions interactives
- L'utilisateur remplit `config.py` (ses amis Instagram, ses artistes Spotify)
- **Copier > Cookiecutter** : la feature clé est `copier update` — si tu améliores la structure de base, les projets dérivés peuvent récupérer les changements. Indispensable pour un projet open-source vivant.
- GitHub Template (bouton "Use this template") = alternative simple mais sans personnalisation ni mise à jour

---

## 2D — Tests & CI

### Stratégie retenue : 2 niveaux

#### 1. Unit Tests (`tests/unit/`)
Valider que les fonctions de parsing/transformation retournent le bon schéma.
```
tests/unit/
├── test_spotify_parser.py     # parse_spotify_json → DataFrame attendu
├── test_instagram_parser.py
└── test_config.py             # WAREHOUSE path résolu correctement
```

#### 2. Data Quality Tests (`tests/data_quality/`)
Valider que les données ingérées sont cohérentes (pas besoin de Great Expectations, des `assert` pandas suffisent pour commencer).
```python
# Exemple
assert df["ts"].notna().all(), "Timestamps manquants dans Spotify"
assert df["track_name"].nunique() > 100, "Trop peu de tracks"
```

#### CI — GitHub Actions
- Déclenché sur chaque PR : lint (ruff) + unit tests
- Pas de tests data quality en CI (données privées non commitées)

### Outils MLOps — ce qui est utile ici

> **Contexte important** : ce projet n'entraîne pas de modèles custom. On utilise CLIP pré-entraîné, ALS via Spark MLlib, et des LLM via API. Les outils de tracking d'entraînement (MLflow, DVC model registry) ne sont donc **pas pertinents**.

| Outil | Usage dans ce projet | Verdict |
|---|---|---|
| **DVC** | Versionner les exports GDPR : savoir quelle version de data correspond à quoi | ⚠️ Utile mais pas prioritaire sans modèles custom |
| **MLflow** | Tracker des entraînements de modèles custom | ❌ Pas pertinent — on n'entraîne rien |
| **LangSmith** | Debugger les prompts du Clone conversationnel, tracker les réponses | ✅ Utile pour la partie LLM — Phase 3 |
| **Kedro** | Structurer les pipelines en nœuds lisibles pour des contributeurs externes | ✅ Oui — mais **gros chantier** (refacto complet des notebooks). Phase 3 uniquement, quand la base est stable |
| **dlhub** | Partage de modèles ML (contexte académique NIST) | ❌ Pas pertinent ici |

**Recommandation Phase 2** : aucun de ces outils maintenant. LangSmith + Kedro en Phase 3 une fois le projet stabilisé et documenté.

---

## 2E — Dashboard : Performance & UX

### Problème 1 — Chargement lent
**Cause probable** : les `layout()` chargent tous les fichiers Parquet/Delta au démarrage.
**Solutions** :
- Lazy loading : ne charger les données qu'au premier accès à la page (callbacks au lieu de layout statique)
- Mettre les données lourdes en cache (`@cache` Flask-Caching ou `dcc.Store`)
- Pré-agréger les données dans des fichiers légers au moment de l'ingestion

### Problème 2 — HTML/CSS dans des strings Python
**Règle** : tout HTML → `app/assets/*.html` chargé via `open()`, tout CSS → `app/assets/*.css` (Dash charge automatiquement).
- Déjà partiellement fait (`social_3d.html`, `style.css`)
- Passer en revue toutes les pages et extraire les styles inline

### Navbar — Réorganisation "Wow vs Tech"

**Idée** : deux sections séparées dans la navbar

```
[ MyDigitalTwin ]   |  EXPLORE : Home · Timeline · Memory Album · Social · Clone
                    |  ANALYSE : Profils · Netflix · Spotify · Psy · Inventaire
```

Ou un toggle **Explore / Analyse** façon mode switcher. À prototyper.

**Pages existantes :**
- Explore (wow) : Home, Timeline, Social, Photos → Memory Album, Clone
- Analyse (data) : Profils, Netflix, Spotify, Psy, Inventaire

---

## 2F — Memory Album (Photos × Musique) ✨

### Vision
Un album photo interactif où chaque moment est associé à une ambiance musicale. L'objectif n'est pas la précision (une photo = une chanson) mais l'**émotion** : une photo festive joue une musique festive. Raviver les synapses.

### Approche technique

#### Données
- **Photos** : export iCloud via privacy.apple.com — sélection manuelle (pas toutes les 2013+)
- **Timestamps EXIF** : date + lieu GPS embarqués dans les métadonnées des photos
- **Spotify** : historique d'écoute avec timestamps déjà disponible

#### Clustering émotionnel (le cœur de la feature)

```
Photos  ──CLIP embeddings──► clusters visuels (festif, nature, intime, voyage, ...)
                                    │
Musiques ──audio features──► clusters musicaux (énergique, mélancolique, festif, ...)
(Spotify API : energy, valence, tempo, danceability)
                                    │
                              Mapping cluster photo → cluster musical
                              (même méthode que CLIP pour les photos, déjà fait)
```

**Spotify Audio Features** (API officielle) :
- `valence` : positivité (0 = triste, 1 = joyeux)
- `energy` : intensité
- `danceability` : festif
- `tempo` : rythme

#### Association temporelle (bonus)
Si une photo date du 14/06/2024 et que Spotify montre une écoute intense ce soir-là → **lier directement**. Sinon, fallback sur le cluster émotionnel.

#### UI — Nouvelle page "Memory Album"
- Grille de photos sélectionnées (avec lazy loading)
- Au survol/clic : lecture d'un extrait musical (Spotify embed ou preview URL)
- Filtres par ambiance (festif, voyage, quotidien, ...)
- Frise chronologique optionnelle

### Actions
- [ ] Script d'import photos iCloud + extraction EXIF (date, GPS)
- [ ] Interface de sélection manuelle des photos (simple script ou mini-UI)
- [ ] Clustering musical via Spotify Audio Features (k-means sur valence/energy/danceability)
- [ ] Mapping cluster photo (CLIP) ↔ cluster musical
- [ ] Association temporelle quand les timestamps coïncident (±12h)
- [ ] Page Dash "Memory Album" + réorganisation navbar

---

## 2G — Topologie (Shape of Me) ✨

### Vision
Représenter le « moi » comme un **espace topologique** plutôt qu'une liste de statistiques. L'idée : trouver la *forme* cachée dans mes données comportementales — les ponts entre habitudes musicales et habitudes de recherche, les clusters d'humeur qui transcendent les plateformes.

### Approche technique : TDA Mapper

**Bibliothèque** : [`tda-mapper-python`](https://github.com/lucasimi/tda-mapper-python)

TDA Mapper construit un graphe où :
- Chaque **nœud** = un cluster d'instants/comportements similaires
- Chaque **arête** = overlap entre clusters (≠ K-Means étanche)
- La **forme** du graphe révèle des structures que le clustering classique masque

```
Sources textuelles
├── spotify_streams     ──sentence-transformers──► embeddings 384D
├── youtube_watch       ──(all-MiniLM-L6-v2)───► embeddings 384D
└── google_searches                               embeddings 384D
         │
         ▼
    UMAP 50D  ←── réduction dimensionnelle avant Mapper (pas 2D !)
         │
         ▼
   TDA Mapper
   ├── Vue 1 : filtre densité    (zones de haute activité)
   ├── Vue 2 : filtre PCA        (axes de variance maximale)
   └── Vue 3 : filtre centroïde  (distance au centre de gravité)
         │
         ▼
  Export JSON graphe → page /topology (3d-force-graph.js)
```

**Autres sources à intégrer :**
- `behavioral_clusters` (clusters K-Means existants comme metadata)
- `photo_clusters` (CLIP embeddings — Phase 2F)
- `social_graph` (graphe Instagram déjà existant)
- `netflix_views` (titres regardés → embeddings)

### Notebooks (`src/scripts/07_topology/`)

| Notebook | Contenu |
|---|---|
| `01_embed_sources.ipynb` | Charger les sources, générer embeddings, réduire avec UMAP 50D |
| `02_mapper_views.ipynb` | Appliquer TDA Mapper, 3 filtres, explorer la forme du graphe |
| `03_export_dashboard.ipynb` | Exporter le graphe JSON pour la page /topology |

### Dashboard — Page `/topology`

Réutilise le pattern `3d-force-graph.js` déjà en place sur la page `/social` :
- Graphe 3D interactif (nœuds = clusters, arêtes = overlap)
- Couleur des nœuds = source dominante (Spotify / YouTube / Google / ...)
- Taille des nœuds = densité (nb d'instants dans le cluster)
- Tooltip au survol : top 3 titres/requêtes du cluster
- Sélecteur de vue : Densité | PCA | Centroïde

### Actions
- [ ] `pip install tda-mapper-python sentence-transformers umap-learn` → ajouter à `requirements/ml.txt`
- [ ] Notebook `01_embed_sources.ipynb` : embeddings Spotify + YouTube + Google
- [ ] Notebook `02_mapper_views.ipynb` : 3 filtres Mapper
- [ ] Notebook `03_export_dashboard.ipynb` : export JSON pour Dash
- [ ] Page Dash `/topology` (réutiliser template `/social`)
- [ ] Ajouter "Topologie" dans la navbar (section Explore)

---

## Horizon inspirationnel — NeuroAI

Ce projet touche à des thèmes au cœur du NeuroAI : représentation de la mémoire épisodique, association multimodale (visuel + auditif), reconstruction de souvenirs par l'émotion. La feature Memory Album est une implémentation concrète de ces concepts (mémoire associative, indexation par l'affect).

Pistes à explorer en parallèle :
- Groupes de recherche : DeepMind (Neuroscience team), Meta AI (FAIR), Mila (Montréal), INRIA
- Mots-clés : *episodic memory*, *multimodal memory consolidation*, *affective computing*
- Stages : garder ce projet comme portfolio concret — il illustre exactement ces problèmes

---

## Priorités suggérées

| Priorité | Tâche | Effort |
|---|---|---|
| 🔴 P0 | Fix dashboard lent + HTML dans strings | 1-2 jours |
| 🔴 P0 | Structure repo + requirements pinnés | ✅ Fait |
| 🟠 P1 | Parsers Instagram / Google / TikTok (overwrite) | 3-4 jours |
| 🟠 P1 | R2 cloud storage | 2-3 jours |
| 🟡 P2 | Unit tests + GitHub Actions CI | 1-2 jours |
| 🟡 P2 | Memory Album (clustering musique + UI) | 5-7 jours |
| 🟡 P2 | Topologie — TDA Mapper (Shape of Me) | 4-6 jours |
| 🟢 P3 | Navbar réorganisation (Explore / Analyse) | 1 jour |
| 🟢 P3 | Ingestion incrémentale (post-stabilisation) | 2-3 jours |
| 🔵 P4 | Copier template | 2 jours |
| 🔵 P4 | LangSmith pour le clone | 1 jour |

---

*Roadmap rédigée le 2026-04-24 — mise à jour le 2026-04-25 (stratégie overwrite dev, Phase 2G Topologie, suppression Amazon).*
