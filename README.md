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
- **Dash / Plotly** — UI Web

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

### Démarrer le Dashboard (Web UI)

Le Dashboard est construit avec Dash/Plotly. Pour le lancer en local :

```bash
# S'assurer d'être dans l'environnement virtuel (si utilisé)
# Activer l'environnement virtuel (.venv/Scripts/activate sur Windows ou source .venv/bin/activate sur Mac/Linux)

# Installer les dépendances si ce n'est pas déjà fait
pip install -r requirements.txt

# Lancer l'application
python -m app.app
```
L'interface sera alors accessible sur [http://localhost:8050](http://localhost:8050).

## Interfaces

| Service | URL |
|---|---|
| Spark Master UI | http://localhost:8080 |
| History Server | http://localhost:18080 |
| Jupyter | http://localhost:8889 |
| Web UI (Dash) | http://localhost:8050 |

## Structure

```text
app/               ← 🖥️ UI Web (Dash)
src/               ← ⚙️ Code d'ingestion, PySpark et ML
 │  ├── scripts/   ← Notebooks PySpark
 │  ├── tools/     ← Outils et scripts utilitaires
 │  └── inventory/ ← Inventaire
infra/             ← 🐳 Fichiers de configuration DevOps/Spark
 │  └── conf/      ← Configuration Spark
data/              ← 💾 Fichiers de données
 │  ├── raw/       ← Fichiers bruts (gitignored)
 │  └── parquet/   ← Datasets nettoyés (entrée ML)
docs/              ← 📖 Plans et idées
warehouse/         ← 🗄️ Delta tables
spark-logs/        ← 📝 Logs Spark
```

## Sources de données

Netflix, Instagram, Amazon, TikTok, Twitter/X, Google, YouTube, Apple, Belfius, Spotify
→ voir `docs/ml_source_plan.md` pour le détail par axe ML.

## Notebooks

| Notebook | Source | Statut |
|---|---|---|
| `netflix.ipynb` | Netflix CSV | ✓ |
| `amazon.ipynb` | Amazon CSV | ✓ |
| `instagram.ipynb` | Instagram JSON | ✓ |
| `google_youtube.ipynb` | Google Takeout HTML | ✓ |
| `apple.ipynb` | Apple Data | ✓ |
| `spotify.ipynb` | Spotify Data | ✓ |
| `tiktok.ipynb` | TikTok Data | ✓ |
| `twitter.ipynb` | Twitter Data | ✓ |
| `parquet_to_delta.ipynb` | Conversion Parquet to Delta | ✓ |
