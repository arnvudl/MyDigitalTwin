# Évolution du Système de Recommandation (Digital Twin)
_Focus : Recommandations Cinéma (Netflix) via MovieLens 32M — Avril 2026_

## 1. L'Approche MovieLens 32M (Big Data) 🚀

L'utilisation du dataset **ml-32m** (32 millions de notes) transforme le projet en un véritable système de recommandation industriel.

*   **Dataset :** `ml-32m` (Grouplens, 2023).
*   **Format de Stockage :** Conversion intégrale en **Parquet** dans le `warehouse` pour des performances optimales avec Spark.
*   **Cible :** `content_type == 'movie'`.

---

## 2. Architecture des Données (Delta Lake / Warehouse) 🏗️

Pour gérer 32 millions de lignes fluidement, les données sont structurées ainsi dans `warehouse/` :

1.  **`warehouse/movielens_ratings/`** : Les 32M de notes (userId, movieId, rating, timestamp).
2.  **`warehouse/movielens_movies/`** : Catalogue mondial (movieId, title, genres).
3.  **`warehouse/movielens_links/`** : Table de correspondance (movieId, imdbId, tmdbId) — *Crucial pour récupérer les posters via TMDB.*

---

## 3. La Nouvelle Stratégie de Recommandation 🧠

### A. Ingestion et Préparation
*   **Conversion CSV → Parquet** : Utilisation de Spark pour lire les fichiers sources `ml-32m` et les réécrire en Parquet partitionné.
*   **Normalisation** : Nettoyage des titres Netflix locaux pour maximiser le "matching" avec le catalogue MovieLens.

### B. Entraînement ALS à Grande Échelle
1.  **Matrice d'Interactions** : Fusion de tes vues Netflix (poids implicite) avec les 32M de notes explicites (échelle 0.5-5.0).
2.  **Hyper-paramètres Spark** : `rank=10`, `maxIter=15`, `regParam=0.1` (à affiner selon les résultats).
3.  **Recommandations** : Génération des 50 meilleurs films non vus par ton profil.

### C. Enrichissement Visual & Sémantique
*   **TMDB Bridge** : Utilisation des `tmdbId` du dataset pour fetcher les affiches et résumés via l'API.
*   **Filtrage Intelligent** : Élimination des films déjà présents dans ton historique Netflix pour ne proposer que de la pure découverte.

---

## 4. Pipeline d'Exécution Technique

```
[ml-32m CSVs] → Notebook Ingestion → [warehouse/movielens_...] (Parquet)
        ↓
Notebook 03_netflix_als_global.ipynb
  - Join : Netflix local + MovieLens Global
  - Spark ALS Training (32M rows)
  - Output : Top Recommendations
        ↓
warehouse/movie_recommendations.parquet
```

**Fichiers mis à jour :**
- ✅ `docs/nouvelle_als.md` : Stratégie 32M.
- 🆕 `src/scripts/01_exploration/ingest_movielens.ipynb` : Notebook à créer pour la conversion CSV → Parquet.
