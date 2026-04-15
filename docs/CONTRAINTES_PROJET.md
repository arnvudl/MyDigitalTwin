# Contraintes & Règles du Projet — MyDigitalTwin

_Document de référence complet — à lire en début de conversation._  
_Mis à jour : 2026-04-13_

---

## Structure du projet

```
MyDigitalTwin/
├── config.py         ← ⚙️  MODIFIER EN PREMIER (chemins + données perso)
├── app/              ← Dashboard Dash Plotly — NE PAS REORGANISER
├── data/
│   ├── raw/          ← Données brutes d'origine — JAMAIS modifier
│   ├── parquet/      ← Intermédiaire phase 01 (converti ensuite en Delta)
│   └── warehouse/    ← Tables Delta/Parquet prêtes à l'emploi
├── src/scripts/
│   ├── 01_exploration/   ← Ingestion par plateforme → data/parquet/
│   ├── 02_clustering/    ← K-Means comportemental → warehouse/
│   ├── 03_als/           ← Recommandations ALS → warehouse/
│   ├── 04_clone/         ← Clone conversationnel RAG
│   ├── 05_CLIP/          ← Clustering photos (pas commencé)
│   └── 06_social/        ← Graphe social Instagram → warehouse/
├── docs/
│   ├── rapport/          ← Rapports techniques par phase
│   └── CONTRAINTES_PROJET.md  ← ce fichier
└── infra/conf/           ← spark-defaults.conf — garder versionné
```

---

## Pipeline d'exécution (ordre obligatoire)

```
01_exploration/ (chaque notebook par plateforme)
    → écrit dans data/parquet/
    ↓
01_exploration/parquet_to_delta.ipynb
    → convertit data/parquet/ → data/warehouse/ (format Delta)
    ↓
02_clustering/ (01 → 02 → 03)
    → lit data/warehouse/, écrit behavioral_clusters + interest_profiles
    ↓
03_als/ (01 → 02)
    → lit data/warehouse/, écrit interactions + als_scores
    ↓
06_social/
    → lit data/raw/INSTAGRAM/, écrit social_graph.parquet
```

---

## Données disponibles dans le warehouse

| Table | Lignes | Source | Utilisée par |
|---|---|---|---|
| `amazon_orders` | 74 | Amazon CSV | timeline |
| `apple_app_installs` | 3 923 | Apple CSV | timeline |
| `apple_signin_apps` | 62 | Apple CSV | — |
| `google_chrome` | 338 | Google Takeout HTML | clustering, timeline |
| `google_searches` | 55 854 | Google Takeout HTML | clustering, timeline |
| `instagram_comments` | 28 | Instagram JSON | — |
| `instagram_likes` | 17 535 | Instagram JSON | clustering, timeline |
| `instagram_messages_meta` | 368 542 | Instagram JSON | — |
| `instagram_saved` | 13 | Instagram JSON | — |
| `netflix_views` | 4 288 | Netflix CSV | ALS, dashboard |
| `spotify_library` | 80 | Spotify JSON | — |
| `spotify_playlists` | 6 475 | Spotify JSON | — |
| `spotify_streams` | 33 972 | Spotify JSON | ALS, clustering, dashboard |
| `tiktok_watch` | 234 771 | TikTok JSON | clustering (limité 2k), timeline |
| `tiktok_likes` | 6 000 | TikTok JSON | timeline |
| `twitter_tweets` | 319 | Twitter JS | timeline |
| `twitter_likes` | 68 534 | Twitter JS | timeline |
| `youtube_watch` | 13 821 | Google Takeout HTML | clustering, timeline |
| `youtube_searches` | 4 991 | Google Takeout HTML | clustering, timeline |
| `behavioral_clusters` | 6 | Phase 02 output | dashboard /profils |
| `interest_profiles` | 6 | Phase 02 output | dashboard / home |
| `interactions` | ~400 items | Phase 03 output | ALS model |
| `als_scores` | ~400 items | Phase 03 output | dashboard /netflix /spotify |
| `social_graph.parquet` | ~128 | Phase 06 output | dashboard /social |

---

## Règles de configuration

### ✅ Toute valeur personnelle ou modulable → `config.py`

Tout ce qui pourrait changer selon l'utilisateur (chemins, listes d'amis, artistes favoris, seuils) doit être dans `config.py` — **jamais hardcodé** dans un notebook.

```python
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname('__file__'), '../../..')))
from config import WAREHOUSE, RAW_DATA, CLOSE_FRIENDS, SPOTIFY_ANCHOR_ARTISTS
```

> **Pourquoi `os.path.dirname('__file__')` et pas `__file__` ?**  
> Dans un notebook Jupyter, `__file__` n'existe pas. La chaîne littérale `'__file__'` retourne `""`,  
> ce qui fait que `os.path.abspath("../../..")` remonte 3 niveaux depuis le CWD du kernel.  
> En Docker, le CWD est `/opt/spark` et les notebooks sont dans `/opt/spark/scripts/XX_phase/`.  
> Jupyter change le CWD vers le dossier du notebook à l'ouverture → `../../..` donne `/opt/spark` ✓  
> En local (hors Docker), même comportement depuis le dossier du notebook.

### ✅ `config.py` doit être monté dans tous les containers Spark

`config.py` n'est pas dans `./src/scripts/` donc il n'est pas couvert par le volume scripts.  
Il est monté **explicitement** dans `docker-compose.yml` pour chaque container Spark :

```yaml
- ./config.py:/opt/spark/config.py
```

**Ne pas supprimer ces lignes du docker-compose** — sans elles, tous les notebooks échouent  
au démarrage avec `ModuleNotFoundError: No module named 'config'`.

**Contenu actuel de `config.py`** :
- `WAREHOUSE` / `RAW_DATA` — chemins auto-calculés depuis la racine
- `CLOSE_FRIENDS` — set des prénoms de dossiers inbox Instagram
- `CLOSE_FRIENDS_MULTIPLIER = 2.0` — boost poids graphe social
- `MIN_MESSAGES = 5` — seuil filtre conversations parasites
- `SPOTIFY_ANCHOR_ARTISTS` — artistes Spotify favoris (ancres ALS)
- `NETFLIX_ANCHOR_TITLES` — films/séries favoris (complète top.md)

---

## Règles Spark

### ❌ Jamais de UDF Python
Sérialise chaque ligne vers Python → catastrophique pour les performances.  
**Alternative** : `F.when()`, `F.regexp_replace()`, `F.expr()` — Column expressions natives compilées JVM.

### ❌ Jamais de `.collect()` dans une boucle
Chaque `.collect()` = un job Spark complet. N itérations = N jobs.  
**Alternative** : `groupBy().agg()` + window function → un seul `.collect()` final.

### ✅ `.cache()` si un DataFrame est utilisé 2x ou plus
Sans cache, Spark relit le Parquet depuis le disque à chaque action.

### ✅ Deux contextes d'exécution

**Phase 01 → Docker cluster** (config dans `spark-defaults.conf`) :
```python
spark = SparkSession.builder \
    .appName("MyDigitalTwin - NomSource") \
    .getOrCreate()
# spark.driver.memory uniquement si volume > 50k lignes ou parsing HTML lourd
```

**Phases 02, 03, 06 → Local standalone** :
```python
spark = SparkSession.builder \
    .appName("MyDigitalTwin-NomPhase") \
    .master("local[*]") \
    .config("spark.driver.memory", "4g") \
    .config("spark.sql.shuffle.partitions", "8") \   # CRITIQUE — défaut=200 absurde sur petits datasets
    .getOrCreate()
```

---

## Contraintes par phase

### Phase 01 — Exploration ✅

- Chaque notebook lit `data/raw/<PLATEFORME>/` et écrit dans `data/parquet/`
- `parquet_to_delta.ipynb` convertit ensuite tout le dossier `data/parquet/` → `data/warehouse/` (Delta Lake)
- Les fonctions `categorize_*()` semblent des UDFs mais retournent des Column expressions (`F.when(...)`) — performances natives
- Schémas explicites (`StructType`) privilégiés sur `inferSchema=True` (évite double lecture)

### Phase 02 — Clustering ✅

- `01_content_clustering` : analyse fréquentielle (K-Means TF-IDF abandonné — Silhouette < 0.15, cluster catch-all 73%)
- `02_behavioral_clustering` : K-Means k=6, features cycliques (sin/cos heure + weekday), StandardScaler, OHE plateforme
- TikTok limité à 2 000 lignes (234k sinon → noie toutes les autres sources)
- `03_fusion_visualization` : extraction keywords par plateforme (unigrammes + bigrammes NGram) pour `interest_profiles`

### Phase 03 — ALS 🔜

- **Approche** : ALS sur **MovieLens 32M + données personnelles** (perso seul → ~400 items, insuffisant)
- **Sources perso** : Spotify + Netflix. YouTube exclu (trop de bruit)
- `user_id = year * 100 + month` — chaque mois = virtual user
- Normalisation plateau entre Spotify (33k) et Netflix (4k) par facteur d'échelle
- Filtre : items vus dans < 2 mois distincts → exclure
- `weight = log1p(play_count)` avant ALS
- Profil via ancres manuelles (pas `model.recommendForUser()` — un seul user réel)
- `implicitPrefs=True`, `rank=20`, `maxIter=20`, `regParam=0.15`
- **Ce qui reste** : intégrer MovieLens 32M, connecter dashboard `/netflix` et `/spotify`
- **Voir** : `docs/rapport/03_als.md` + `docs/nouvelle_als.md` + `src/scripts/03_als/PLAN.md`

### Phase 04 — Clone 🔜 (V5 RAG)

- **Approche** : RAG + Gemini 1.5 Flash (fine-tuning abandonné — voir `docs/rapport/04_clone.md` pour le pourquoi)
- `sentence-transformers` (`all-MiniLM-L6-v2`) indexe 300 exemples de conversations
- 3 exemples de style injectés dans le prompt Gemini à chaque message
- `05_export_for_gemini.py` prépare le corpus
- **Cette phase ne touche pas Spark**
- **Ce qui reste** : indexation FAISS/cosine, connexion `/clone` dashboard
- **Voir** : `docs/rapport/04_clone.md` + `docs/selection_corpus_clone.md` + `src/scripts/04_clone/STATUS.md`

### Phase 05 — CLIP ⏳ (pas commencé)

- **Modèle** : `openai/clip-vit-large-patch14` (embeddings 768 dims)
- **Input** : photos depuis `data/raw/INSTAGRAM/`
- **Pipeline prévu** : CLIP local → embeddings → K-Means Spark ML → labelling text similarity → `data/warehouse/photo_clusters.parquet`
- **Voir** : `src/scripts/05_CLIP/PLAN.md`

### Phase 06 — Social ✅

- Pandas pur (pas Spark — parsing JSON par fichier, ~100 nœuds)
- `CLOSE_FRIENDS` et `MIN_MESSAGES` depuis `config.py`
- Poids = `message_count × 2` pour close friends, `message_count × 1` sinon

---

## Dashboard — pages et sources

| Page | Source warehouse | Statut |
|---|---|---|
| `/` Home | `interest_profiles`, `behavioral_clusters` | ✅ Live |
| `/profils` | `behavioral_clusters`, `interest_profiles` | ✅ Live |
| `/social` | `social_graph.parquet` | ✅ Live |
| `/timeline` | toutes les tables horodatées | ✅ Live |
| `/netflix` | `netflix_views`, `als_scores` | 🔜 Phase 03 |
| `/spotify` | `spotify_streams`, `als_scores` | 🔜 Phase 03 |
| `/recommandations` | `als_scores` | 🔜 Phase 03 |
| `/clone` | API Gemini 1.5 Flash + RAG | 🔜 Phase 04 |
| `/photos` | `photo_clusters.parquet` | ⏳ Phase 05 |

---

## Fichiers à ne pas toucher

| Chemin | Raison |
|---|---|
| `app/` | Dashboard en production — ne pas réorganiser |
| `data/raw/` | Données brutes — jamais modifier |
| `infra/conf/spark-defaults.conf` | Config cluster Spark — volontairement versionné |
| `docs/roadmap.md` | Vue projet globale — mise à jour manuelle |
| `docs/clone_finetuning.md` | Décisions techniques clone V1-V3 |
| `docs/selection_corpus_clone.md` | Guide sélection corpus clone |
| `src/scripts/04_clone/STATUS.md` | Historique complet des versions clone |
