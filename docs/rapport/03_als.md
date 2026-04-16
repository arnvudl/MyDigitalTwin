# Phase 03 — Système de Recommandation ALS

_Dossier_ : `src/scripts/03_als/`  
_Statut_ : ✅ Terminé  
_Notebooks_ : `01_build_interactions`, `02_als_model`, `03_movie_recommendations`  
_Scripts_ : `als_fast_local.py`  
_Outputs_ : `data/warehouse/interactions`, `data/warehouse/als_scores`, `data/warehouse/movie_recommendations.parquet`

---

## Objectif

Produire un score de recommandation personnalisé "Arnaud aimera à X%" pour les films Netflix, exploitable dans le dashboard (`/netflix`).

---

## Évolution de l'approche

### Ce qui a été abandonné : ALS sur données personnelles uniquement

Une première version utilisait uniquement les données Netflix perso pour entraîner l'ALS. Le problème : **~400 items distincts** après filtre — trop peu pour que la factorisation de matrice converge vers quelque chose de significatif. ALS a besoin de co-occurrences riches (item X vu par plusieurs utilisateurs), impossible avec un seul utilisateur réel.

### Approche retenue : SVD sur MovieLens 32M + données personnelles

On fusionne les **32 millions de notes MovieLens** (base collaborative mondiale) avec les vues personnelles Netflix pour entraîner un modèle global. Deux implémentations existent :

| Implémentation | Fichier | Usage |
|---|---|---|
| **SVD scipy/implicit** (production) | `als_fast_local.py` | Machine locale — résultats en <1 min |
| **ALS Spark** (référence serveur) | `03_movie_recommendations.ipynb` | Cluster distribué 10+ serveurs |

---

## Pipeline complet — Vue d'ensemble

```
01_build_interactions.ipynb
  └─ Source : Netflix (YouTube exclu)
  └─ Virtual users = mois (user_id = year*100 + month)
  └─ Filtre : items vus ≥ 2 mois distincts
  └─ Output : warehouse/interactions (Parquet)
         │
         ▼
02_als_model.ipynb
  └─ ALS Spark sur interactions Netflix (virtual users)
  └─ Ancres Netflix → vecteur de référence → similarité cosinus
  └─ Output : warehouse/als_scores
         │
         ▼
03_movie_recommendations.ipynb  ──(cellule 4)──► warehouse/tmp_als_matrix
  └─ ALS Spark sur MovieLens 32M + vues perso Netflix (userId=0)
  └─ Output : warehouse/movie_recommendations/ (dossier Parquet)
  └─ [OPTIONNEL] Si Spark sature :
         │
         ▼
als_fast_local.py                ◄── lit tmp_als_matrix (écrit par cellule 4)
  └─ SVD scipy sur la même matrice (sans Spark)
  └─ Output : warehouse/movie_recommendations.parquet (même fichier cible)
```

**Deux sources de recommandations utilisées dans le dashboard :**

| Source | Fichier | Alimente |
|---|---|---|
| `als_scores` | `02_als_model.ipynb` | Moteur de recherche d'affinité Netflix |
| `movie_recommendations.parquet` | `als_fast_local.py` ou notebook 03 | Top 10 films recommandés |

---

## Évolution de l'optimisation : Spark → Python pur

### Étape 1 — Spark (notebooks 02 et 03)

Les notebooks utilisent PySpark pour rester scalables vers un cluster :

- `02_als_model.ipynb` : `local[*]`, `shuffle.partitions=8`, 4 Go driver — volume faible (~15k interactions)
- `03_movie_recommendations.ipynb` : `local[*]`, `shuffle.partitions=100`, 8 Go driver — 10-15M de lignes après filtrage dense

Optimisations Spark appliquées dans les deux notebooks :

| Technique | Où | Pourquoi |
|---|---|---|
| `broadcast()` sur filtres | Notebook 03, cellule 4 | Les DataFrames pop_movies et pwr_users sont petits (<10k lignes) — évite un shuffle complet |
| `.cache()` sur interactions_agg | Notebook 01 | Consommé deux fois (stats + filtre) |
| `.cache()` sur `combined` | Notebook 03, cellule 4 | Matrice relue par ALS à chaque itération |
| `checkpointInterval=2` | Notebook 03, cellule 5 | Coupe la lignée DAG toutes les 2 itérations — évite OOM/StackOverflow |
| `percent_rank()` window function | Notebooks 02 et 03 | Normalisation 0-100 sans `.count()` séparé (économise un job Spark) |
| Column expressions natives | Partout | Jamais de UDF Python — exécution JVM, pas de sérialisation Python |
| Filtrage dense (≥1000 notes/film, ≥200 notes/user) | Notebook 03, cellule 4 | Réduit 32M → ~10-15M de lignes utiles, matrice plus dense |

### Étape 2 — Fallback Python pur (`als_fast_local.py`)

Quand l'entraînement ALS Spark sature la RAM locale (8-12 Go), `als_fast_local.py` prend le relais. Il ne réimplémente pas tout le pipeline — il **réutilise `tmp_als_matrix`** (la matrice combinée écrite par la cellule 4 du notebook 03) et remplace uniquement l'entraînement + la génération de recommandations.

| Aspect | ALS Spark (notebook 03) | SVD scipy (`als_fast_local.py`) |
|---|---|---|
| Framework | PySpark (JVM) | Pandas + scipy (BLAS/MKL natif) |
| Algorithme | ALS itératif | SVD tronquée (`svds`) |
| Rang | 8 | 50 |
| Temps (local) | ~20 min, 12 Go RAM | < 1 min, ~2 Go RAM |
| Scalabilité | Cluster distribué | Machine locale uniquement |
| Dépendance | Autonome | Nécessite `tmp_als_matrix` du notebook 03 |

---

## Architecture finale

### `als_fast_local.py` — SVD local (utilisé en production)

- Lit `tmp_als_matrix` (matrice combinée MovieLens + perso)
- Décomposition SVD `scipy.sparse.linalg.svds` (rang 50)
- Reconstruction des scores pour `userId=0` (Arnaud)
- Top 200 → enrichissement titre/genres/tmdbId → normalisation 0-100
- **Écrit** : `warehouse/movie_recommendations.parquet`

**Hyperparamètres SVD :**

| Paramètre | Valeur | Justification |
|---|---|---|
| `k` (rang) | 50 | Plus élevé que l'ALS Spark (rank=8) — pas de contrainte RAM ici, capture plus de dimensions latentes |
| Top N généré | 200 | Pool large avant sélection des 50 finaux enregistrés |
| Normalisation | Min-max 0-100 | Appliquée sur les 200, sauvegarde des 50 premiers |

**Performance** : <1 min, ~2 Go RAM. Là où Spark sature 12 Go en 20 min.

### `03_movie_recommendations.ipynb` — ALS Spark (référence cluster)

- Session `local[*]` 8 Go (simulation standalone — scalable vers cluster)
- Filtrage dense : films ≥1 000 notes + power users ≥200 notes
- `broadcast()` sur les DataFrames de filtres (petits — quelques milliers de lignes)
- Checkpoint Spark toutes les 2 itérations (évite l'explosion du DAG)
- `percent_rank()` window function pour le scoring (évite `.count()` séparé)
- Normalisation `content_type` insensible à la casse (`F.lower()`) pour robustesse
- ALS : `rank=8`, `maxIter=10`, `regParam=0.1`, `implicitPrefs=False`
- **Écrit** : `warehouse/movie_recommendations/` (format dossier Parquet)

---

## Choix de l'algorithme

### Pourquoi ALS/SVD ?

ALS (Alternating Least Squares) et SVD (Singular Value Decomposition) sont les deux faces de la factorisation matricielle. SVD est mathématiquement plus direct et beaucoup plus léger en local (BLAS/MKL pur, pas de JVM).

### Pourquoi "explicite" (pas implicite) pour MovieLens ?

MovieLens contient des notes explicites (0.5-5.0). On utilise ces notes directement (`implicitPrefs=False`) — plus fiable que de convertir un signal continu en binaire implicite.

### Pourquoi pas du Deep Learning (NCF, BERT4Rec) ?

- Ces modèles surpassent ALS à partir de plusieurs millions d'interactions **personnelles**.
- Avec un seul utilisateur réel, on n'a pas ce volume même avec MovieLens comme pont.
- ALS/SVD est interprétable et auditable.

---

## Construction des Interactions (`01_build_interactions`)

### Source : Netflix uniquement

YouTube exclu malgré ses 13 000 lignes — trop de bruit (pubs, vidéos auto-play).

### Virtual Users = Mois

`user_id = year * 100 + month` : chaque mois d'activité = profil distinct. Permet à ALS de détecter les évolutions temporelles des goûts.

### Filtre : items vus dans >= 2 mois distincts

Items vus un seul mois = signal potentiellement aléatoire.

### Optimisations Spark

- `.cache()` sur `interactions_agg` : le DataFrame est consommé deux fois (stats + filtre bruit). Le cache évite une relecture complète depuis Parquet.
- `local[*]` + `shuffle.partitions=8` : adapté au volume (~15 000 interactions finales).
- Toutes les transformations sont des Column expressions Spark natif — pas de UDF Python.

---

## Modèle ALS (`02_als_model`)

### Hyperparamètres

| Paramètre | Valeur | Justification |
|---|---|---|
| `rank` | 20 | Dimension des vecteurs latents. |
| `maxIter` | 20 | Convergence suffisante sur ce volume. |
| `regParam` | 0.15 | Régularisation L2 anti-overfitting. |
| `implicitPrefs` | True | Données comportementales (vues Netflix). |

### Log scaling

`weight = log1p(play_count)` : compresse les valeurs extrêmes sans perdre l'ordonnancement.

### Pipeline 100% Spark natif

Le moteur de scoring est entièrement en Spark sans UDF Python :

| Étape | Technique Spark |
|---|---|
| Normalisation des titres | `regexp_replace` + `lower` + `trim` (Column expressions) |
| Matching des ancres | `broadcast()` + `contains()` croisé sur deux colonnes normalisées |
| Similarité cosinus | `zip_with` + `aggregate` + `transform` (higher-order array functions) |
| Boost des ancres | `join` left + `when()` / `otherwise()` |
| Normalisation 0-100 | `percent_rank()` window function (évite un `.count()` séparé) |

**Vecteur de référence** : seule étape sur le driver — collecte des vecteurs des items d'ancrage (petit volume, N_ancres lignes) puis moyenne numpy. Le reste du scoring s'effectue sur le cluster Spark.

---

## Diagnostic de Stabilité (Avril 2026)

### Pourquoi l'entraînement Spark sur 16.8M crashait

1. **Explosion du DAG** : ALS itératif accumule les opérations en mémoire. Sans checkpoint fréquent, le Driver s'effondre (StackOverflow ou OOM).
2. **Sous-partitionnement** : `shuffle.partitions=8` sur 16.8M = blocs massifs → crashs JVM.

### Solutions appliquées au notebook Spark

- `checkpointInterval=2` : coupe la lignée toutes les 2 itérations
- `spark.sql.shuffle.partitions=100` : granularité adaptée
- Filtres de densification (`≥1000 notes/film`, `≥200 notes/user`) : réduit à ~10-15M de lignes utiles
- `broadcast()` sur les DataFrames de filtres (petits — quelques milliers de lignes)

### Pourquoi le sampling aléatoire à 10% détruit la qualité

En supprimant 90% des notes aléatoirement, on crée une matrice trop creuse. Les "ponts" de co-occurrence disparaissent : un film qui avait 100 notes n'en a plus que 10, insuffisant pour définir son vecteur latent.

---

## Dashboard — `/netflix`

La page `/netflix` intègre désormais tout :
- Timeline de visionnages filtrable (année / mois / semaine)
- Top séries et films
- Section "Recommandé pour toi" : top 10 + moteur de recherche d'affinité
  - Top 10 : depuis `movie_recommendations.parquet` (SVD MovieLens 32M)
  - Recherche : depuis `als_scores` (scores personnels Netflix)

La page `/recommandations` séparée a été supprimée — tout est consolidé dans `/netflix`.

---

## Ce qui a été fait

- [x] Ingestion MovieLens 32M → warehouse (`01_exploration/ingest_movielens.ipynb`)
- [x] Construction interactions Netflix (`01_build_interactions.ipynb`)
- [x] ALS scores personnels Netflix (`02_als_model.ipynb`)
- [x] Pipeline SVD local MovieLens (`als_fast_local.py`) — production
- [x] Pipeline ALS Spark local (`03_movie_recommendations.ipynb`) — référence serveur
- [x] Dashboard `/netflix` avec section recommandations intégrée
