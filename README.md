# MyDigitalTwin

Analyse ML de donnees personnelles multi-plateformes pour construire un jumeau numerique interactif.

Dashboard actuel:

- clustering comportemental
- graphe social
- recommandations Netflix / Spotify
- clone conversationnel
- exploration photo / CLIP

---

## Stack

| Composant | Outil |
|---|---|
| Traitement de donnees | PySpark 3.5.x + Delta Lake |
| Machine Learning | Spark MLlib, CLIP |
| Dashboard | Dash / Plotly |
| Clone conversationnel | Corpus DM + Gemini |
| Infra locale | Docker Compose |

---

## Configuration du projet

Le projet se configure sans modifier le code Python.

### 1. Fichiers de config

- Copier `config.yaml.example` vers `config.yaml`
- Copier `.env.example` vers `.env`

### 2. Que mettre dans chaque fichier

`config.yaml`

- identite Instagram
- `close_friends`
- artistes d'ancrage Spotify
- conversations du clone

`.env`

- `GEMINI_API_KEY`
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `TMDB_API_KEY`
- optionnel: `DASH_HOST`, `DASH_PORT`

### 3. Modele de configuration

- `config.py`: configuration runtime centrale, chemins derives, chargement des secrets
- `config.yaml`: donnees personnelles non secretes
- `.env`: secrets

Les chemins `WAREHOUSE`, `PROCESSED_DATA` et `LLM_DATA` se calculent automatiquement selon l'environnement local ou Docker.

---

## Flux de donnees

Le projet suit maintenant ce pipeline:

1. `data/inbox/`
   Depots bruts des exports GDPR decompresses
2. `data/processed/`
   Donnees re-rangees par source et jeux prepares manuellement
3. `data/warehouse/`
   Tables Parquet / Delta consommees par notebooks et dashboard

---

## Installation

### Prerequis

- Python 3.11+
- Java 11+
- Docker Desktop optionnel

### Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Demarrage rapide

### 1. Deposer les exports

Deposer les archives ou dossiers decompresses dans `data/inbox/`.

Exemples attendus:

- `instagram-*`
- `takeout-*`
- `spotify-*`
- `tiktok-*`
- `twitter-*`
- `NetflixViewingHistory.csv`

### 2. Lancer l'ingestion locale

```bash
python -m src.ingestion.run_all
```

Cette etape deplace les donnees vers `data/processed/`.

### 3. Lancer les notebooks

Ordre recommande:

```text
src/scripts/01_exploration/
src/scripts/02_clusters/
src/scripts/03_als/
src/scripts/05_CLIP/
src/scripts/06_social/
src/scripts/07_psy/
```

Lancer Jupyter:

```bash
jupyter notebook
```

### 4. Lancer le dashboard

```bash
python -m app.app
```

Par defaut:

- Dashboard: [http://localhost:8050](http://localhost:8050)

---

## Docker

```bash
make up
make dev
make down
```

Services par defaut:

- Spark Master UI: [http://localhost:8080](http://localhost:8080)
- History Server: [http://localhost:18080](http://localhost:18080)
- Jupyter: [http://localhost:8889](http://localhost:8889)
- Dashboard: [http://localhost:8050](http://localhost:8050)

> Sous Windows, garder `entrypoint.sh` en fins de ligne LF.

---

## Photos / CLIP

Le flux photo Instagram attendu est:

1. ingestion Instagram vers `data/processed/INSTAGRAM/...`
2. collecte des photos pour tri manuel
3. tri manuel dans `data/processed/INSTAGRAM/CLIP_SORTING/`
4. embeddings CLIP puis clustering

Script de collecte:

```bash
python src/scripts/05_CLIP/00_collect_photos.py
```

---

## Structure du projet

```text
config.py
config.yaml
.env
app/
src/
  ingestion/
  scripts/
data/
  inbox/
  processed/
  warehouse/
docs/
infra/
```

---

## Documentation

- `docs/ROADMAP_PHASE2.md`
- `docs/CONFIG_AUDIT_PHASE2.md`
- `docs/rapport/`
