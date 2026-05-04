# Phase 01 — Ingestion & Exploration des Données Personnelles

_Dossier_ : `src/scripts/01_exploration/`  
_Statut_ : ✅ Terminé  
_Notebooks_ : `amazon`, `apple`, `google_youtube`, `instagram`, `netflix`, `spotify`, `tiktok`, `twitter`, `parquet_to_delta`

---

## Objectif

Lire toutes les données brutes exportées depuis chaque plateforme, les nettoyer, les normaliser, et les écrire dans le **warehouse** (`data/warehouse/`) au format Parquet — qui sert de couche de stockage pour toutes les phases suivantes.

---

## Pourquoi Spark plutôt que Pandas ?

Même si les volumes (quelques milliers à quelques centaines de milliers de lignes) pourraient techniquement tenir en Pandas, le choix de **PySpark** est délibéré pour plusieurs raisons :

1. **Scalabilité anticipée** : TikTok seul représente 234 000 lignes. Instagram messages : 368 000 entrées. En ajoutant l'axe MovieLens (32 millions de notes), Pandas deviendrait rapidement un goulot d'étranglement.
2. **Cohérence du pipeline** : Les phases suivantes (clustering, ALS) utilisent Spark ML. Travailler en Spark dès l'ingestion évite des conversions coûteuses `toPandas()` / `createDataFrame()` en cours de pipeline.
3. **Lazy evaluation** : Spark ne calcule rien tant qu'une action n'est pas déclenchée, ce qui permet d'enchaîner des transformations complexes sans coût intermédiaire.
4. **Format Parquet** : Columnar, compressé, avec schéma embarqué — idéal pour des lectures sélectives (ex. : lire uniquement `event_hour` pour le clustering comportemental, sans charger toutes les colonnes).

---

## Architecture : Pourquoi un Warehouse ?

Au départ, les transformations écrivaient directement des fichiers `.parquet` dans `data/parquet/`. L'introduction d'un **warehouse** (`data/warehouse/`) apporte :

- **Nomenclature stable** : chaque source = un dossier nommé (`spotify_streams`, `youtube_watch`, etc.). Les notebooks des phases suivantes lisent toujours `read_table("spotify_streams")` sans se soucier du chemin d'origine.
- **Séparation des responsabilités** : `data/raw/` = données brutes d'origine (jamais modifiées), `data/warehouse/` = données transformées prêtes à l'emploi.
- **Idempotence** : chaque notebook écrit avec `.mode("overwrite")`, donc re-exécutable à tout moment sans double-comptage.

## Configuration SparkSession en phase 01

Les notebooks d'exploration tournent **dans le cluster Docker** (Spark master + worker définis par `docker-compose.yml`). La configuration Spark est centralisée dans `infra/conf/spark-defaults.conf` — le notebook se connecte au master existant sans avoir à le redéfinir.

C'est pourquoi les SparkSessions de phase 01 sont minimalistes (juste `.appName()`) : tout le reste (master URL, shuffle partitions, mémoire executor) est injecté par le cluster.

**Exceptions justifiées :**

| Notebook | Config ajoutée | Raison |
|---|---|---|
| `google_youtube` | `spark.driver.memory = 6g` | BeautifulSoup parse du HTML Google Takeout en mémoire driver — fichiers HTML volumineux |
| `instagram` | `spark.driver.memory = 4g` | 368 000 lignes messages_meta |
| `tiktok` | `spark.driver.memory = 4g` | 234 000 lignes watch history |
| `parquet_to_delta` | Extensions Delta | Obligatoires pour écrire le format Delta Lake (`DeltaCatalog` + `DeltaSparkSessionExtension`) |

Les notebooks sans config explicite (`amazon`, `netflix`, `spotify`, `twitter`, `apple`) traitent de petits volumes (< 35k lignes) et n'ont pas besoin de surcharger les defaults du cluster.

---

## Évolution : Parquet → Delta Lake

Les notebooks d'exploration écrivent d'abord en **Parquet pur**. Après avoir étudié Delta Lake dans le cours, le notebook `parquet_to_delta.ipynb` relit tous les fichiers Parquet du warehouse et les réécrit en **format Delta**.

**Pourquoi ce choix après coup ?**

Delta Lake apporte ce que le Parquet seul ne peut pas offrir :
- **Transactions ACID** : les écritures sont atomiques — pas de fichiers corrompus si le job plante en cours.
- **Versioning (Time Travel)** : `spark.read.format("delta").option("versionAsOf", 0).load(...)` permet de relire une version antérieure du warehouse.
- **Schema enforcement** : Delta rejette une écriture dont le schéma ne correspond pas au schéma existant — évite les bugs silencieux.
- **Optimisation des petits fichiers** : `OPTIMIZE` + `ZORDER` pour accélérer les lectures sur les grandes tables.

La migration est non destructive : les dossiers Parquet existants sont relus, Delta écrit dans les mêmes chemins avec les métadonnées `_delta_log/` en plus.

---

## Choix techniques par source

### Schémas explicites vs `inferSchema`

Pour la majorité des sources (Netflix, Spotify, Amazon), les schémas sont **déclarés explicitement** (`StructType` + `StructField`). Raisons :
- `inferSchema=True` déclenche un scan complet du fichier pour déduire les types → double lecture, coût inutile.
- Les exports de plateformes ont des types ambigus (ex. : dates ISO 8601 sous forme de String → on préfère parser explicitement avec `to_timestamp()`).

### Nettoyage des dates

Toutes les colonnes temporelles sont parsées en `TimestampType` puis décomposées en champs utiles : `event_hour`, `event_weekday`, `event_year`, `event_month`. Cette décomposition est faite dès l'ingestion pour ne pas la répéter dans chaque phase downstream.

### Catégorisation des produits/apps (Amazon, Apple)

Les fonctions `categorize_product()` et `categorize_app()` semblent être des UDFs Python, mais **ce ne sont pas des UDFs Spark**. Elles retournent une expression `Column` PySpark (`F.when(...).when(...)`) compilée en SQL natif côté JVM. Aucun aller-retour Python/JVM par ligne — c'est aussi performant qu'une colonne calculée en SQL.

### Colonnes supprimées

Chaque notebook drop les colonnes inutiles analytiquement (identifiants internes, adresses, métadonnées de livraison, etc.). Cela réduit la taille Parquet et le bruit dans les phases downstream.

---

## Outputs du Warehouse

| Table | Lignes | Source brute |
|---|---|---|
| `amazon_orders` | 74 | CSV Amazon |
| `apple_app_installs` | 3 923 | CSV Apple |
| `apple_signin_apps` | 62 | CSV Apple |
| `google_chrome` | 338 | JSON Chrome |
| `google_searches` | 55 854 | JSON Google |
| `instagram_comments` | 28 | JSON Instagram |
| `instagram_likes` | 17 535 | JSON Instagram |
| `instagram_messages_meta` | 368 542 | JSON Instagram |
| `instagram_saved` | 13 | JSON Instagram |
| `netflix_views` | 4 288 | CSV Netflix |
| `spotify_library` | 80 | JSON Spotify |
| `spotify_playlists` | 6 475 | JSON Spotify |
| `spotify_streams` | 33 972 | JSON Spotify |
| `tiktok_watch` | 234 771 | JSON TikTok |
| `tiktok_likes` | 6 000 | JSON TikTok |
| `twitter_tweets` | 319 | JS Twitter |
| `youtube_watch` | 13 821 | JSON Google |
| `youtube_searches` | 4 991 | JSON Google |

---

## Décisions notables

**TikTok (234k lignes)** : volume élevé dû au scroll continu. Dans les phases suivantes (clustering comportemental), on limite à 2 000 échantillons via `.limit(2000)` pour éviter que TikTok "noie" toutes les autres sources dans le clustering.

**Instagram messages_meta (368k)** : colonne `content` non exploitée directement (contenu des messages trop sensible). On garde uniquement les métadonnées temporelles et de volume pour le graphe social (phase 06).

**Twitter (319 tweets)** : volume trop faible pour un axe dédié. Données conservées dans le warehouse mais non utilisées dans les phases ML actuelles.
