# AXE 2 — Recommandations ALS (MovieLens 32M)
_Mis à jour : 2026-04-15_

---

## Objectif

Donner un titre de film → score **"Arnaud aimera à X%"** + top recommandations non vus.

Modèle : **ALS** (Alternating Least Squares) de `pyspark.ml.recommendation`, entraîné sur MovieLens 32M + données personnelles Netflix.

---

## Pourquoi MovieLens 32M ?

Les données personnelles seules (~4 288 vues Netflix) sont insuffisantes pour entraîner un ALS robuste — pas assez de signal inter-items. En fusionnant avec les 32M de notes MovieLens, l'ALS apprend des similarités entre films à grande échelle, puis le profil personnel ancre les recommandations.

---

## Données sources

### Externes — MovieLens 32M (à télécharger sur grouplens.org)
| Fichier source | → Warehouse | Contenu |
|---|---|---|
| `ml-32m/ratings.csv` | `warehouse/movielens_ratings/` | 32M notes (userId, movieId, rating, timestamp) |
| `ml-32m/movies.csv` | `warehouse/movielens_movies/` | Catalogue mondial (movieId, title, genres) |
| `ml-32m/links.csv` | `warehouse/movielens_links/` | movieId ↔ imdbId ↔ tmdbId |

### Personnelles — Warehouse existant
| Table | Items | Signal |
|---|---|---|
| `netflix_views` | show_title (films uniquement) | interaction implicite |

---

## Pipeline

```
[ml-32m CSVs]
    ↓
src/scripts/01_exploration/ingest_movielens.ipynb   [À CRÉER]
  - Lecture CSV Spark → écriture Parquet partitionné
  - Cible : content_type == 'movie' uniquement
  → warehouse/movielens_ratings/ + movielens_movies/ + movielens_links/

warehouse/movielens_* + netflix_views
    ↓
01_build_interactions.ipynb                          [À METTRE À JOUR]
  - Normalisation titres Netflix → matching MovieLens
  - Fusion : notes explicites (0.5-5.0) + vues Netflix (poids implicite)
  - StringIndexer sur movieId (ALS exige des entiers)
  → warehouse/als_interactions.parquet

    ↓
02_als_model.ipynb                                   [À METTRE À JOUR]
  - Spark ALS : rank=10, maxIter=15, regParam=0.1, implicitPrefs=True
  - Filtrage : films déjà vus exclus
  - Top 50 recommandations
  → warehouse/movie_recommendations.parquet

    ↓
app/pages/netflix.py + recommandations.py            [À CRÉER]
  - Enrichissement affiches + résumés via API TMDB (tmdbId depuis links)
```

---

## Contraintes techniques

- ALS nécessite des IDs entiers → `StringIndexer` sur movieId
- `implicitPrefs=True` pour les vues Netflix (feedback implicite)
- Cold start : nouveaux films sans notes MovieLens → pas de prédiction
- Un seul utilisateur réel → ALS utilisé en **item-based similarity** (pas collaborative inter-users)
- Spark config locale : `spark.sql.shuffle.partitions=8`, `spark.driver.memory=8g` (32M lignes)

---

## Dashboard — pages concernées

### `/recommandations`
- Top films recommandés non vus, avec affiche TMDB + score prédit
- Input : titre → score "Arnaud aimera à X%"

### `/netflix`
- Timeline des visionnages
- Top genres, top films, top séries
- Stats : streak, heure moyenne, durée totale

---

## Fichiers

| Fichier | Statut | Contenu |
|---|---|---|
| `top.md` | ✅ Référence | Films/séries favoris (ancres profil) |
| `01_build_interactions.ipynb` | 🔜 À mettre à jour | Fusion MovieLens + Netflix local |
| `02_als_model.ipynb` | 🔜 À mettre à jour | Entraînement ALS 32M |
| `01_exploration/ingest_movielens.ipynb` | 🔜 À créer | Ingestion CSV → Parquet |
| `app/pages/netflix.py` | 🔜 À créer | Page dashboard Netflix |
| `app/pages/recommandations.py` | 🔜 À créer | Page scores ALS + affiches |
| `_outdated/01b_semantic_enrichment.py` | ❌ Archivé | Enrichissement Ollama (remplacé par TMDB) |

**Voir aussi** : `docs/nouvelle_als.md` pour l'architecture détaillée.
