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

Une première version utilisait uniquement les données perso (Spotify + Netflix) pour entraîner l'ALS. Le problème : **~400 items distincts** après filtre — trop peu pour que la factorisation de matrice converge vers quelque chose de significatif. ALS a besoin de co-occurrences riches (item X vu par plusieurs utilisateurs), impossible avec un seul utilisateur réel.

### Approche retenue : SVD sur MovieLens 32M + données personnelles

On fusionne les **32 millions de notes MovieLens** (base collaborative mondiale) avec les vues personnelles Netflix pour entraîner un modèle global. Deux implémentations existent :

| Implémentation | Fichier | Usage |
|---|---|---|
| **SVD scipy/implicit** (production) | `als_fast_local.py` | Machine locale — résultats en <1 min |
| **ALS Spark** (référence serveur) | `03_movie_recommendations.ipynb` | Cluster distribué 10+ serveurs |

---

## Architecture finale

### `als_fast_local.py` — SVD local (utilisé en production)

- Lit `tmp_als_matrix` (matrice combinée MovieLens + perso)
- Décomposition SVD `scipy.sparse.linalg.svds` (rang 50)
- Reconstruction des scores pour `userId=0` (Arnaud)
- Top 200 → enrichissement titre/genres/tmdbId → normalisation 0-100
- **Écrit** : `warehouse/movie_recommendations.parquet`

**Performance** : <1 min, ~2 Go RAM. Là où Spark sature 12 Go en 20 min.

### `03_movie_recommendations.ipynb` — ALS Spark (référence cluster)

- Session `local[*]` 8 Go (simulation standalone — scalable vers cluster)
- Filtrage dense : films ≥1 000 notes + power users ≥200 notes
- Broadcasts sur les filtres de densification (`broadcast()`)
- Checkpoint Spark toutes les 2 itérations (évite l'explosion du DAG)
- `percent_rank()` window function pour le scoring (évite `.count()` séparé)
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

### Sources retenues : Spotify + Netflix uniquement

YouTube exclu malgré ses 13 000 lignes — trop de bruit (pubs, vidéos auto-play).

### Virtual Users = Mois

`user_id = year * 100 + month` : chaque mois d'activité = profil distinct. Permet à ALS de détecter les évolutions temporelles des goûts.

### Normalisation des plateformes

Sans normalisation, Spotify (33k streams) écraserait Netflix (4k views). Facteur d'échelle par plateforme (`max_count / platform_count`).

### Filtre : items vus dans >= 2 mois distincts

Items vus un seul mois = signal potentiellement aléatoire.

---

## Modèle ALS (`02_als_model`)

### Hyperparamètres

| Paramètre | Valeur | Justification |
|---|---|---|
| `rank` | 20 | Dimension des vecteurs latents. |
| `maxIter` | 20 | Convergence suffisante sur ce volume. |
| `regParam` | 0.15 | Régularisation L2 anti-overfitting. |
| `implicitPrefs` | True | Données comportementales (Spotify + Netflix perso). |

### Log scaling

`weight = log1p(play_count)` : compresse les valeurs extrêmes sans perdre l'ordonnancement.

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
  - Recherche : depuis `als_scores` (scores personnels Spotify + Netflix)

La page `/recommandations` séparée a été supprimée — tout est consolidé dans `/netflix`.

---

## Ce qui a été fait

- [x] Ingestion MovieLens 32M → warehouse (`01_exploration/ingest_movielens.ipynb`)
- [x] Construction interactions virtuelles Spotify + Netflix (`01_build_interactions.ipynb`)
- [x] ALS scores personnels (`02_als_model.ipynb`)
- [x] Pipeline SVD local MovieLens (`als_fast_local.py`) — production
- [x] Pipeline ALS Spark local (`03_movie_recommendations.ipynb`) — référence serveur
- [x] Dashboard `/netflix` avec section recommandations intégrée
