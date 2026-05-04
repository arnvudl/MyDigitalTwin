# Guide Setup

Ce guide explique comment reproduire le pipeline MyDigitalTwin avec tes propres
données.

## 1. Cloner le projet

```bash
git clone <repo-url>
cd MyDigitalTwin
```

## 2. Configurer le projet

```bash
cp .env.example .env
cp config.yaml.example config.yaml
```

Modifier `config.yaml` pour les paramètres personnels non secrets :

- nom et username Instagram
- close friends
- artistes d'ancrage Spotify
- conversations du clone
- labels CLIP et catégories comportementales

Modifier `.env` pour les secrets :

- `GEMINI_API_KEY`
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `TMDB_API_KEY`

## 3. Demander et préparer les exports

Télécharger les exports des plateformes, les dézipper, puis déposer les dossiers
bruts dans `data/inbox/`.

Exports supportés :

| Source | Export à demander |
|---|---|
| Instagram | Toutes les informations, format JSON, période au choix, qualité média moyenne |
| Google Takeout | Chrome, Ads, Mon activité, Compte Google, YouTube |
| Spotify | Données de compte |
| TikTok | Export complet, tout sélectionner |
| Twitter/X | DM uniquement si tu veux limiter l'export |
| Netflix | CSV de l'activité de visionnage |

Structure attendue :

```text
data/inbox/
  instagram-*/
  takeout-*/
  spotify-*/
  tiktok-*/
  twitter-*/
  NetflixViewingHistory.csv
```

Ne modifie pas les exports à la main. Les parsers d'ingestion normalisent
l'arborescence.

## 4. Lancer Docker

```bash
docker compose up --build
```

Services :

- Dashboard : http://localhost:8050
- Jupyter : http://localhost:8889
- Spark UI : http://localhost:8080
- Spark History : http://localhost:18080

## 5. Lancer l'ingestion

Depuis Docker :

```bash
docker compose exec spark-master python3 -m src.ingestion.run_all
```

Ou en local sous Windows :

```bash
.\.venv\Scripts\python.exe -m src.ingestion.run_all
```

L'ingestion scanne `data/inbox/`, déplace les fichiers détectés vers
`data/processed/<SOURCE>/`, puis écrit `data/ingestion_log.json`.

Limiter l'ingestion à une ou plusieurs sources :

```bash
docker compose exec spark-master python3 -m src.ingestion.run_all --sources instagram google spotify
```

## 6. Lancer l'analyse

Utiliser Jupyter pour exécuter les notebooks et scripts dans cet ordre :

```text
src/scripts/01_exploration/
src/scripts/02_clusters/
src/scripts/03_memory_album/
src/scripts/04_clone/
src/scripts/05_CLIP/
src/scripts/06_social/
src/scripts/07_psy/
```

Les sorties générées arrivent dans :

- `data/warehouse/`
- `data/LLM_DATA/`
- `app/assets/`

## 7. Ouvrir le dashboard

```bash
docker compose up dashboard
```

Puis ouvrir http://localhost:8050.

## 8. Relances incrémentales

Instagram, Google et Spotify sont cumulatifs. Les fichiers déjà présents dans
`data/processed/` sont conservés, et seuls les nouveaux fichiers de
`data/inbox/` sont déplacés.

TikTok, Twitter/X et Netflix sont des exports complets. Un export plus récent
remplace la version déjà traitée.

## 9. Mode dev local

Docker reste le runtime recommandé. Pour un environnement local léger :

```bash
python.exe -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## 10. Nettoyer Instaloader et warehouse local

Le code actuel ne référence pas Instaloader. Si un dossier `instaloader/`
apparaît, vérifier les logs Docker et les volumes locaux :

```bash
docker compose logs
docker compose exec spark-master find /opt/spark -maxdepth 3 -iname '*instaloader*'
```

`.dockerignore` ne nettoie pas ces dossiers. Il sert seulement à réduire le
contexte envoyé au build Docker. Il ne doit pas ignorer `data/`, car Spark et le
dashboard s'appuient sur ce dossier. Pour supprimer les dossiers locaux non
voulus :

```powershell
Remove-Item -Recurse -Force -LiteralPath .\data\instaloader, .\instaloader, .\warehouse -ErrorAction SilentlyContinue
```

`.\warehouse` désigne le dossier `warehouse/` à la racine du repo.
`data/warehouse/` est différent : c'est une sortie normale du pipeline. Le
supprimer force à régénérer les tables et artefacts analytiques.
