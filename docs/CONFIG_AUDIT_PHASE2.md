# Audit Configuration - Phase 2G

Date: 2026-04-28

## Objectif

Documenter l'audit du point `2. Reproductibilite & Configuration` de la roadmap avant refactor du code.

## Resume

Le projet dispose deja d'un noyau de configuration utile via `config.py`, `config.yaml` et `.env`, mais plusieurs modules contournent encore cette source de verite. Le probleme principal n'est pas l'absence de configuration, mais la duplication de logique de chemins, de secrets et de detection d'environnement.

## Points positifs

- `config.py` centralise deja plusieurs chemins projet, secrets et parametres perso.
- `config.yaml.example` couvre une partie importante des parametres utilisateur.
- `.env.example` couvre les secrets principaux.
- Les parsers d'ingestion sont plutot propres et assez peu hardcodes.

## Problemes identifies

### 1. Duplication de la logique local/Docker dans `app/`

Plusieurs pages Dash recalculent elles-memes `data/warehouse`, `data/processed` ou `/app/data/...` au lieu d'importer `config.py`.

Fichiers concernes:

- `app/app.py`
- `app/pages/home.py`
- `app/pages/social.py`
- `app/pages/netflix.py`
- `app/pages/photos.py`
- `app/pages/spotify.py`
- `app/pages/clusters.py`
- `app/pages/timeline.py`
- `app/pages/psy.py`
- `app/pages/clone.py`
- `app/spotify_utils.py`

Risque:

- divergence entre comportement local, Docker app et Docker Spark ;
- maintenance plus couteuse ;
- bugs discrets quand un chemin est corrige dans un seul endroit.

### 2. Secrets relus directement dans l'app

Certains modules appellent `load_dotenv()` ou `os.getenv()` directement, alors que `config.py` charge deja `.env`.

Fichiers concernes:

- `app/pages/netflix.py`
- `app/pages/clone.py`
- `app/spotify_utils.py`

Risque:

- messages d'erreur non uniformes ;
- plusieurs points d'entree pour les memes secrets ;
- comportement incoherent selon l'ordre d'import.

### 3. Incoherence `raw` / `processed`

Le projet a migre vers un flux `inbox -> processed -> warehouse`, mais certains endroits restent ambigus.

Cas releves:

- `config.py` maintient `RAW_DATA = PROCESSED_DATA` pour retrocompatibilite ;
- le notebook social lit l'inbox Instagram via `RAW_DATA` ;
- la page `social` utilisait un chemin `raw` en local ;
- le script CLIP lisait dans `data/raw/INSTAGRAM/...`.

Risque:

- confusion pour un nouveau contributeur ;
- divergence entre notebooks et app ;
- erreurs lors d'une reinstallation propre du projet.

### 4. Documentation plus alignee avec le code

Le `README.md` indiquait encore d'editer `config.py` directement, alors que l'orientation cible est `config.yaml` + `.env`.

Problemes releves:

- instruction obsolete autour de `config.py` ;
- mention de `NETFLIX_ANCHOR_TITLES` absente du `config.py` courant ;
- certains champs attendus par `config.py` ne sont pas visibles dans `config.yaml.example`.

### 5. Parametres d'execution encore hardcodes

Certains scripts et notebooks gardent en dur des valeurs d'execution ou des conventions de chemins.

Exemples:

- bootstrap repetitif pour retrouver `config.py` dans les notebooks ;
- parametres Spark repetes (`local[*]`, memoire driver, partitions) ;
- chemins CLIP et chemins de cache definis localement dans les modules.

## Decisions recommandees

### A. Faire de `config.py` l'unique point d'entree runtime

Y centraliser:

- chemins runtime (`DATA_ROOT`, `WAREHOUSE`, `PROCESSED_DATA`, `LLM_DATA`) ;
- chemins metier derives (Instagram inbox, topics, personnalisation X, caches, assets de donnees) ;
- secrets applicatifs ;
- options runtime simples (`DASH_HOST`, `DASH_PORT`).

### B. Clarifier la frontiere des fichiers de config

- `config.py`: constantes projet, chemins derives, chargement des secrets, helpers simples ;
- `config.yaml`: donnees personnelles non secretes et preferences utilisateur ;
- `.env`: secrets et identifiants sensibles.

### C. Normaliser le flux de donnees

Flux cible:

- `data/inbox/` pour les exports entrants ;
- `data/processed/` pour les donnees reorganisees et les jeux prepares manuellement ;
- `data/warehouse/` pour les tables consommees par notebooks et app.

Implication specifique CLIP:

- les photos Instagram a trier manuellement doivent vivre dans `data/processed/INSTAGRAM/CLIP_SORTING/`.

### D. Refactor par couches

Ordre recommande:

1. `config.py`
2. modules Python de `app/`
3. scripts Python hors notebooks
4. documentation utilisateur
5. notebooks

## Plan de refactor immediate

1. Ajouter les constantes runtime manquantes dans `config.py`.
2. Faire consommer `config.py` a l'app Dash.
3. Corriger le flux CLIP pour `processed/INSTAGRAM/CLIP_SORTING`.
4. Realigner `README.md` et `config.yaml.example`.
5. Laisser une seconde passe pour harmoniser les notebooks.

## Hors scope de cette premiere passe

- refonte complete de tous les notebooks ;
- externalisation complete des parametres Spark ;
- validation automatique du schema `config.yaml`.
