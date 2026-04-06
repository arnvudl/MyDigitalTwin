# AXE 2 — Recommandations ALS
_Priorité : haute — données déjà disponibles dans le warehouse_

---

## Objectif

Donner un titre de film ou de musique → obtenir un score **"Arnaud aimera à X%"**.

Modèle : **ALS** (Alternating Least Squares) de `pyspark.ml.recommendation`.  
ALS apprend des patterns implicites à partir de l'historique de consommation.  
Il prédit un score de préférence pour tout item non encore consommé.

---

## Données sources (warehouse)

| Table | Items | Signal implicite |
|---|---|---|
| `spotify_streams` | artistName + trackName | msPlayed → weight |
| `netflix_views` | show_title | interaction_weight |
| `youtube_watch` | title | interaction_weight |
| `instagram_likes` | — | like = signal faible |
| `tiktok_watch` | — | watch = signal faible |

Signal implicite = on ne sait pas si l'item a été aimé, seulement consommé.  
→ Pondération : écoute complète > écoute partielle, visionnage > scroll.

---

## Pipeline

```
warehouse/spotify_streams + netflix_views + youtube_watch
        ↓
01_build_interactions.ipynb
  - Unification : (user_id=0, item_id, weight)
  - item_id = hash(platform + title)
  - Filtrage : items vus < 3 fois exclus (bruit)
        ↓
warehouse/interactions.parquet
        ↓
02_als_model.ipynb
  - ALS(rank=50, maxIter=20, regParam=0.1, implicitPrefs=True)
  - Split train/test (80/20 par timestamp)
  - Évaluation : NDCG@10
        ↓
warehouse/als_scores.parquet
  (item_id, item_title, platform, predicted_score, rank)
        ↓
03_dashboard_pages.ipynb  (optionnel — ou directement dans app/)
  - Top recommandations par catégorie
  - Wrapped custom par période
```

---

## Dashboard — pages concernées

### `/recommandations`
- Input : titre libre (musique ou film)
- Output : score 0–100% + top 10 recommandations similaires
- Bonus : "Tu n'as pas encore vu/écouté…" avec score prédit

### `/netflix`
- Timeline des visionnages
- Top genres, top séries, top films
- Streak de visionnage, heure moyenne

### `/spotify`
- **Wrapped custom** : choisir une période → top artistes, top titres, minutes écoutées
- Évolution mensuelle des artistes favoris
- Distribution horaire d'écoute

---

## Contraintes techniques

- ALS nécessite des IDs entiers (StringIndexer sur item_title)
- `implicitPrefs=True` → feedback implicite (pas de rating explicite)
- Cold start : nouveaux items sans historique → pas de prédiction possible
- Un seul utilisateur (toi) → ALS n'a pas de "collaborative filtering" inter-users  
  → On utilise ALS comme **item-based similarity** : items co-consommés → proches

---

## Fichiers à créer

| Fichier | Contenu |
|---|---|
| `01_build_interactions.ipynb` | Unification + nettoyage interactions |
| `02_als_model.ipynb` | Entraînement ALS + évaluation |
| `app/pages/netflix.py` | Page dashboard Netflix |
| `app/pages/spotify.py` | Page dashboard Spotify + Wrapped |
| `app/pages/recommandations.py` | Page scores ALS |
