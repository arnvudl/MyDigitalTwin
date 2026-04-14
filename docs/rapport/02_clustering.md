# Phase 02 — Clustering Comportemental & Profils d'Intérêts

_Dossier_ : `src/scripts/02_clustering/`  
_Statut_ : ✅ Terminé  
_Notebooks_ : `01_content_clustering`, `02_behavioral_clustering`, `03_fusion_visualization`  
_Outputs_ : `data/warehouse/behavioral_clusters`, `data/warehouse/interest_profiles`

---

## Configuration SparkSession en phase 02

Contrairement à la phase 01 (Docker cluster), les notebooks de clustering tournent **en local standalone**, ce qui nécessite une config explicite :

```python
SparkSession.builder
    .master("local[*]")                          # utilise tous les cœurs CPU locaux
    .config("spark.driver.memory", "4g")         # défaut = 1g, insuffisant pour le ML
    .config("spark.sql.shuffle.partitions", "8") # défaut = 200 → absurde pour quelques milliers de lignes
    .getOrCreate()
```

**Pourquoi `shuffle.partitions = 8` ?**  
Le paramètre par défaut est **200**. Lors d'un `groupBy` ou d'un `join`, Spark crée 200 partitions de shuffle. Sur nos datasets (quelques milliers à 80 000 lignes), cela produit 200 micro-fichiers quasi vides — overhead réseau et disque considérable. Avec 8 partitions, chaque partition a une taille raisonnable et le job termine 3-5x plus vite.

**Pourquoi `local[*]` explicite ?**  
Sans `.master()`, Spark cherche un cluster Spark distant (défini dans `spark-defaults.conf` pour Docker). En dehors du cluster, il faut forcer le mode local.

---

## Objectif

Identifier des **profils comportementaux** (moments, habitudes, plateformes) à partir des données d'activité multi-sources, et en extraire des **centres d'intérêts** lisibles pour le dashboard.

---

## Ce qu'on a abandonné : TF-IDF + K-Means "content"

Le `01_content_clustering.ipynb` représente une tentative de clustering **sémantique** : extraire des mots-clés (TF-IDF) depuis les titres YouTube, Google, Spotify, et les regrouper en K-Means.

**Pourquoi ça n'a pas fonctionné** :
- Les titres sont hétérogènes (YouTube mélange pubs, clips, streams ; Google mélange requêtes en français/anglais/flamand).
- Le TF-IDF donne des clusters trop "lexicaux" (ex. : un cluster entier sur le mot "official") plutôt que des thèmes réels.
- Les clusters étaient instables selon k (Silhouette score < 0.15).

**La décision** : passer à un clustering **comportemental** (sur les patterns temporels et plateformes) plutôt que sémantique. Le sémantique est traité en post-hoc via extraction fréquentielle par cluster.

---

## Approche retenue : K-Means Comportemental

### Features choisies

| Feature | Justification |
|---|---|
| `hour_sin`, `hour_cos` | Encodage cyclique de l'heure (0h = 24h = même voisinage). Un encodage linéaire ferait croire que 23h et 0h sont éloignés. |
| `weekday_sin`, `weekday_cos` | Même logique pour les jours (lundi ≈ dimanche dans un cycle hebdomadaire). |
| `platform_ohe` | One-Hot Encoding de la plateforme. `handleInvalid="keep"` pour éviter que des nouvelles plateformes crashent le pipeline. |
| `weight_norm` | Pondération par interaction (ex. : `msPlayed` pour Spotify pondère l'écoute longue plus que le skip). |

**Pourquoi `StandardScaler`** : les features temporelles (sin/cos) sont dans `[-1, 1]` mais `weight_norm` peut dépasser 1. Sans normalisation, le poids dominerait la distance euclidienne du K-Means.

### Pourquoi k=6 ?

- Testé avec k=4 à k=10 via Silhouette Score et inertie (méthode "coude").
- k=6 donne **Silhouette = 0.32**, meilleur compromis entre granularité et séparation.
- 6 clusters correspondent intuitivement aux grands blocs de la semaine : matin/après-midi/soir × semaine/weekend.

### Optimisation : élimination de la boucle Python (24 jobs → 2)

La première version de la caractérisation des clusters utilisait une boucle Python :
```python
for cluster_id in range(6):
    subset = beh_df.filter(col == cluster_id)
    subset.count()              # job 1
    subset.agg(avg("hour"))     # job 2
    subset.agg(avg("weekday"))  # job 3
    subset.groupBy("platform")  # job 4
```
Soit **24 Spark jobs** (4 actions × 6 clusters), chacun relisant le DataFrame depuis le début du DAG.

**Remplacé par** :
1. Un seul `groupBy("beh_cluster").agg(count, avg_hour, avg_weekday)` → **1 job**.
2. Un window `row_number().over(partitionBy("beh_cluster").orderBy(desc("cnt")))` pour les top plateformes → **1 job**.

Gain : 24 → 2 jobs Spark.

---

## Fusion & Extraction des Centres d'Intérêts (03_fusion_visualization)

### Pourquoi `.cache()` sur les DataFrames sources

Les DataFrames `youtube_df`, `google_df`, `chrome_df`, `spotify_df`, `netflix_df` sont chacun relu **2 à 3 fois** dans la même cellule (une fois pour `extract_top_words`, une fois pour `extract_bigrams`, une fois pour `extract_samples`).

Sans `.cache()`, Spark relit le Parquet depuis le disque à chaque action. Avec `.cache()`, le DataFrame est maintenu en mémoire JVM après la première lecture. Sur 5 sources × 3 lectures = 15 lectures → 5 lectures avec cache.

### Extraction des mots-clés : unigrammes + bigrammes

- **Unigrammes** avec `StopWordsRemover` (anglais + français + liste de bruit custom).
- **Bigrammes** via `NGram(n=2)` pour capturer des entités nommées : "travis scott", "one piece", "premier league".
- Les deux sont fusionnés en dédoublonnant (un mot ne peut pas apparaître deux fois dans le profil).

### Outputs

| Table | Contenu | Utilisée par |
|---|---|---|
| `behavioral_clusters` | 6 profils (label, emoji, avg_hour, plateformes dominantes) | `home.py` — section profils |
| `interest_profiles` | 6 profils + keywords + exemples top items | `home.py` — remplacement dict `CATEGORY_KEYWORDS` hardcodé |

---

## Résultats des 6 Clusters

| ID | Label | Items | Heure moy. | Plateformes |
|---|---|---|---|---|
| 0 | YouTube · Après-midi | ~13 000 | 14h | youtube |
| 1 | Soirée connectée | ~31 000 | 19h | google, netflix, instagram |
| 2 | TikTok · Scroll | ~2 000 | 14h | tiktok (limité) |
| 3 | Spotify · Journée | ~34 000 | 13h | spotify |
| 4 | Navigation · Soir | ~340 | 20h | chrome |
| 5 | Recherches · Journée | ~30 000 | 14h | google |

*Note : TikTok est limité à 2 000 échantillons pour ne pas écraser les autres plateformes dans le clustering (234k lignes vs ~14k pour YouTube).*
