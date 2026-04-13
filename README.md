# MyDigitalTwin

Analyse ML de données personnelles multi-plateformes pour construire un jumeau numérique interactif.

**Dashboard live** : clustering comportemental, graphe social, recommandations ALS, clone conversationnel.

---

## Stack

| Composant | Outil |
|---|---|
| Traitement de données | PySpark 3.5.5 + Delta Lake |
| Machine Learning | Spark MLlib (K-Means, ALS) |
| Dashboard | Dash / Plotly |
| Clone conversationnel | RAG + Gemini 1.5 Flash |
| Infra locale | Docker Compose (Spark master + worker + history) |

---

## Tu veux refaire ce projet avec tes propres données ?

### 1. Exporter tes données personnelles

Chaque plateforme a une page "Télécharger mes données" dans les paramètres :

| Plateforme | Où | Format attendu |
|---|---|---|
| **Google** | [myaccount.google.com/data-and-privacy](https://myaccount.google.com/data-and-privacy) → Google Takeout | HTML/JSON |
| **Spotify** | Paramètres → Confidentialité → Télécharger tes données | JSON |
| **Netflix** | [netflix.com/account](https://www.netflix.com/account) → Confidentialité → Télécharger tes informations personnelles | CSV |
| **Instagram** | Paramètres → Activités → Télécharger tes informations | JSON |
| **TikTok** | Paramètres → Confidentialité → Données personnalisées | JSON |
| **Amazon** | [amazon.fr/gp/privacycentral](https://www.amazon.fr/gp/privacycentral) | CSV |
| **Apple** | [privacy.apple.com](https://privacy.apple.com) | CSV |
| **Twitter/X** | Paramètres → Ton compte → Télécharger une archive | JS |

Décompresse tout dans `data/raw/` en respectant cette structure :
```
data/raw/
├── GOOGLE/          ← Google Takeout décompressé
├── SPOTIFY/
├── NETFLIX/
├── INSTAGRAM/
├── TIKTOK/
├── AMAZON/
├── APPLE/
└── X/
```

### 2. Configurer le projet

**Ouvre `config.py` à la racine** et change :
- `CLOSE_FRIENDS` → tes amis proches (prénoms des dossiers inbox Instagram)
- `SPOTIFY_ANCHOR_ARTISTS` → tes artistes Spotify favoris
- `NETFLIX_ANCHOR_TITLES` → tes séries/films Netflix favoris

Les chemins (`WAREHOUSE`, `RAW_DATA`) se calculent automatiquement depuis la racine du projet.

### 3. Installer les dépendances

```bash
# Créer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux

pip install -r requirements.txt
```

**Prérequis système** :
- Python 3.11+
- Java 11 (requis par Spark) → `java -version` pour vérifier
- Docker Desktop (optionnel, pour le cluster Spark)

### 4. Exécuter les notebooks dans l'ordre

```
src/scripts/01_exploration/   → un notebook par plateforme (ingestion → warehouse)
src/scripts/02_clustering/    → 01 → 02 → 03 (clustering comportemental)
src/scripts/03_als/           → 01 → 02 (recommandations)
src/scripts/06_social/        → 01 (graphe social Instagram)
```

Lancer Jupyter :
```bash
jupyter notebook
```

### 5. Lancer le dashboard

```bash
python -m app.app
```
Accessible sur [http://localhost:8050](http://localhost:8050)

---

## Démarrage avec Docker (cluster Spark)

```bash
make up       # Build et démarrage
make dev      # Shell dans le master
make down     # Arrêt et nettoyage
```

| Service | URL |
|---|---|
| Spark Master UI | http://localhost:8080 |
| History Server | http://localhost:18080 |
| Jupyter | http://localhost:8889 |
| Dashboard | http://localhost:8050 |

> **Windows** : si tu modifies `entrypoint.sh`, garde les fins de ligne en LF (pas CRLF).

---

## Structure du projet

```
config.py          ← ⚙️  À modifier en premier (chemins + données perso)
app/               ← 🖥️  Dashboard Dash/Plotly
src/scripts/       ← 📓  Notebooks PySpark par phase
data/
├── raw/           ← 📥  Exports bruts des plateformes (gitignored)
└── warehouse/     ← 🗄️  Tables Parquet transformées (gitignored)
docs/
├── rapport/       ← 📖  Rapports techniques par phase
└── CONTRAINTES_PROJET.md  ← règles et contexte du projet
infra/             ← 🐳  Config Spark
```

---

## Documentation technique

| Document | Contenu |
|---|---|
| `docs/rapport/01_exploration.md` | Pourquoi Spark, pourquoi un warehouse |
| `docs/rapport/02_clustering.md` | K-Means comportemental, choix de k=6 |
| `docs/rapport/03_als.md` | ALS implicite, MovieLens 32M |
| `docs/rapport/04_clone.md` | Historique fine-tuning → RAG Gemini |
| `docs/rapport/06_social.md` | Graphe social Instagram |
| `docs/CONTRAINTES_PROJET.md` | Règles Spark, contraintes par phase |
