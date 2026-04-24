# MyDigitalTwin — Roadmap Phase 2 : Data Engineering

> **Contexte** : Le PoC (Phase 1) est terminé. Le dashboard tourne, les notebooks explorent les données Spotify, Instagram, Netflix, Apple, Amazon, YouTube, TikTok, Twitter. Phase 2 = industrialiser, pérenniser, enrichir.

---

## Vue d'ensemble

```
Phase 2
├── 2A  Infrastructure & Stockage cloud
├── 2B  Ingestion incrémentale & GDPR reminders
├── 2C  Qualité du code & Reproductibilité
├── 2D  Tests & CI
├── 2E  Dashboard — Performance & UX
└── 2F  Memory Album (Photos × Musique)
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

## 2B — Ingestion incrémentale & GDPR Reminders

### Principe : ingestion incrémentale
Chaque source de données a un cycle d'export différent. L'ingestion ne repart **jamais de zéro** — elle détecte ce qui est nouveau et l'ajoute au warehouse (merge Delta Lake ou append Parquet).

### Sources & fréquences conseillées

| Source | Mécanisme export | Fréquence suggérée |
|---|---|---|
| **Spotify** | API officielle (déjà connectée) | Hebdomadaire (automatisable) |
| **Instagram** | GDPR export → email | Mensuelle |
| **Netflix** | GDPR export → email | Trimestrielle |
| **Apple / iCloud** | privacy.apple.com → email | Semestrielle |
| **Amazon** | GDPR export → email | Semestrielle |
| **YouTube** | Google Takeout → email | Trimestrielle |
| **TikTok** | GDPR export → email | Trimestrielle |
| **Twitter/X** | GDPR export → email | Trimestrielle |

### GDPR Reminders (semi-automatique)
Les plateformes envoient les données par email → impossible de tout automatiser proprement sans scraping fragile. Solution pragmatique :

- **Script `remind.py`** : affiche les sources dont le dernier export date de plus de N jours
- **Optionnel** : reminder via email/notif (cron local ou GitHub Actions scheduled)
- Chaque ingestion logge la date dans un fichier `data/ingestion_log.json`

```json
{
  "spotify": {"last_run": "2026-04-20", "rows_added": 142},
  "instagram": {"last_run": "2026-01-15", "rows_added": 0}
}
```

### Actions
- [ ] Créer `src/ingest/` avec un module par source (`spotify.py`, `instagram.py`, ...)
- [ ] Implémenter logique de merge incrémental (Delta Lake `MERGE INTO` ou pandas dedup)
- [ ] Créer `ingestion_log.json` et `remind.py`
- [ ] Ajouter iCloud Photos comme nouvelle source (export EXIF + sélection manuelle)

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
| 🔴 P0 | Structure repo + requirements pinnés | 0.5 jour |
| 🟠 P1 | Ingestion incrémentale + ingestion_log | 3-4 jours |
| 🟠 P1 | R2 cloud storage + DVC | 2-3 jours |
| 🟡 P2 | Unit tests + GitHub Actions CI | 1-2 jours |
| 🟡 P2 | MLflow pour ALS | 1 jour |
| 🟢 P3 | Memory Album (clustering musique + UI) | 5-7 jours |
| 🟢 P3 | Navbar réorganisation | 1 jour |
| 🔵 P4 | Cookiecutter template | 2 jours |
| 🔵 P4 | LangSmith pour le clone | 1 jour |

---

*Roadmap rédigée le 2026-04-24 — à réviser à chaque fin de sprint.*
