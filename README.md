# MyDigitalTwin

Analyse ML de données personnelles multi-plateformes pour construire un jumeau numérique.

```
docker exec -it spark-master /bin/bash  
```

## Objectifs

| Axe | Modèle | Output |
|---|---|---|
| Clone NLP | TF-IDF + N-grams | Profil de style d'écriture |
| Oracle des recommandations | ALS | Prédictions de contenu |
| Dashboard des "Moi" | K-Means | Clusters comportementaux |

## Stack

- **PySpark 3.5.5** + Delta Lake
- **Docker Compose** — cluster Spark local (master + worker + history server)
- Python 3.11, BeautifulSoup (`lxml`), PyArrow

## Démarrage rapide

```bash
# Build et démarrage du cluster
make up

# Shell dans le master
make dev

# Arrêt et nettoyage complet
make down
```

> **Note Windows** : si tu modifies `entrypoint.sh`, assure-toi que les fins de ligne restent en LF (pas CRLF), sinon le conteneur ne démarre pas.

## Interfaces

| Service | URL |
|---|---|
| Spark Master UI | http://localhost:8080 |
| History Server | http://localhost:18080 |
| Jupyter | http://localhost:8889 |

## Structure

```
data/raw/          ← fichiers bruts (gitignored)
data/parquet/      ← datasets nettoyés (entrée ML)
scripts/notebook/  ← notebooks PySpark d'ingestion et ML
docs/              ← plans et idées
warehouse/         ← Delta tables
```

## Sources de données

Netflix, Instagram, Amazon, TikTok, Twitter/X, Google, YouTube, Apple, Belfius
→ voir `docs/ml_source_plan.md` pour le détail par axe ML.

## Notebooks

| Notebook | Source | Statut |
|---|---|---|
| `netflix.ipynb` | Netflix CSV | ✓ |
| `amazon.ipynb` | Amazon CSV | ✓ |
| `instagram.ipynb` | Instagram JSON | ✓ |
| `google_youtube.ipynb` | Google Takeout HTML | En cours |