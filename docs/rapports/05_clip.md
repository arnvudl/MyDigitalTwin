# Phase 05 — Clustering Photos CLIP

_Dossier_ : `src/scripts/05_CLIP/`  
_Statut_ : ✅ Terminé (V1 PCA+KMeans → V2 UMAP+HDBSCAN, labels manuels)  
_Dernière mise à jour_ : 2026-04-16

---

## Objectif

Grouper les photos Instagram par thème visuel (soirées, concerts, voyages, selfies, sport...) via les embeddings du modèle CLIP, et afficher ces clusters dans la page `/photos` du dashboard.

---

## Choix du modèle : CLIP (openai/clip-vit-large-patch14)

### Pourquoi CLIP et non un CNN classique ?

Un CNN classique (ResNet, EfficientNet) produit des embeddings visuels généraux, mais CLIP produit des embeddings dans un **espace commun image-texte**. Cela permet :
- De labelliser automatiquement les clusters : comparer les centroïdes aux embeddings de textes descriptifs ("photo de soirée", "photo de concert", "selfie") via cosine similarity.
- D'obtenir des clusters sémantiquement cohérents (CLIP a été entraîné sur 400M de paires image-texte).

### Pourquoi `clip-vit-large-patch14` ?

- Modèle ViT-L (Large) = 768 dimensions d'embedding, meilleure représentation que ViT-B (512 dims).
- `CLIPVisionModelWithProjection` retourne `.image_embeds` directement en tensor — API stable contrairement à `CLIPModel.get_image_features()` qui retourne un objet `BaseModelOutputWithPooling` selon la version de transformers.

---

## Pipeline

```
photos Instagram (JPG)
    ↓
01_clip_embeddings.ipynb
    CLIPVisionModelWithProjection — mapInPandas (une fois par partition)
    embeddings 768-dim L2-normalisés
    → data/warehouse/photo_embeddings/ (Parquet)
    ↓
02_clip_clustering.ipynb
    Spark : lecture embeddings → .collect() → numpy
    UMAP (n_components=50) → réduction dimensionnelle non-linéaire
    HDBSCAN → clustering densité, outliers = -1
    Labelling manuel via inspection visuelle des clusters
    → data/warehouse/photo_clusters/ (Parquet)
    ↓
Dashboard /photos
    Scatter UMAP 2D interactif, galerie filtrée par cluster
```

---

## Embeddings — `01_clip_embeddings.ipynb`

### Config Spark

```python
spark.driver.memory              = "4g"
spark.sql.shuffle.partitions     = "8"
spark.sql.parquet.compression.codec = "snappy"
```

- **`driver.memory = 4g`** : les embeddings finaux (2 419 × 768 floats) pèsent ~7 Mo — la mémoire est largement suffisante. La vraie pression vient du modèle CLIP (~1.7 Go par worker chargé dans `embed_partition`), pas du DataFrame Spark lui-même.
- **`shuffle.partitions = 8`** : `mapInPandas` ne génère pas de shuffle — ce paramètre est sans effet dans ce pipeline. Conservé par cohérence avec les autres notebooks.
- **`snappy`** : codec de compression Parquet. Rapide en lecture et écriture, bon rapport vitesse/taux pour des données float. Préféré à `gzip` (meilleur taux mais plus lent) ou à aucune compression.

### BATCH_SIZE et N_PARTITIONS

```python
BATCH_SIZE   = 32   # images par appel modèle
N_PARTITIONS = 4    # workers Spark = chargements du modèle
```

- **`BATCH_SIZE = 32`** : bon équilibre mémoire GPU/CPU vs overhead de chargement image. Monter à 64 sur GPU avec >8 Go VRAM ; descendre à 16 si OOM.
- **`N_PARTITIONS = 4`** : le modèle CLIP est chargé **une fois par partition**. 4 partitions = 4 chargements du modèle (~1.7 Go chacun). Augmenter si cluster multi-nœuds ; garder bas en local pour éviter l'OOM.

### CUDA vs CPU

```python
device = "cuda" if torch.cuda.is_available() else "cpu"
```

- **CUDA** : si un GPU est disponible (ex : cluster avec GPU), l'inférence est ~10x plus rapide qu'en CPU. Sur 2 419 photos en batch 32, ça passe de ~20 min à ~2 min.
- **CPU** : fallback automatique pour Docker sans GPU ou machine locale. Aucune configuration manuelle nécessaire — `torch.cuda.is_available()` détecte l'environnement au runtime.
- La détection se fait **à l'intérieur de `embed_partition`** (exécuté sur le worker), pas sur le driver — chaque worker choisit son device indépendamment.

### Pourquoi `mapInPandas` et non une Column expression

`mapInPandas` est l'exception justifiée à la règle no-UDF : le modèle PyTorch doit être chargé en Python pur, il n'existe pas d'équivalent JVM. Le gain est que le modèle est chargé **une fois par partition** (pas par ligne) — 4 chargements pour 2 419 photos.

- **Input** : `data/raw/INSTAGRAM/CLIP_SORTING/` — 2 419 photos triées manuellement
- **Modèle** : `CLIPVisionModelWithProjection` + `CLIPImageProcessor`
- **Output** : `data/warehouse/photo_embeddings/` — 2 419 lignes, schema `(path, filename, embedding: Array<float>)`

---

## Clustering — V1 : PCA + KMeans ❌ Abandonné

### Ce qui a été testé

| Paramètre | Valeur |
|---|---|
| Réduction | PCA 50D (MLlib) |
| Variance expliquée | 62.6% |
| Algorithme | KMeans k=5 (MLlib) |
| Silhouette score | 0.1400 |

### Résultats (inspection visuelle)

| Cluster | Label auto | Réalité observée |
|---|---|---|
| 0 | concert ou festival | soirées entre amis |
| 1 | soirée entre amis | soirées entre amis |
| 2 | concert ou festival | soirées entre amis (doublon) |
| 3 | selfie portrait | ✅ propre, peu d'outliers |
| 4 | sport et fitness | ❌ fourre-tout : voitures, famille, nourriture, paysages, dessins |

### Pourquoi ça échoue

**PCA** est une réduction **linéaire** — elle projette dans les directions de variance maximale globale. Elle ne préserve pas la structure locale des groupes : des photos visuellement proches (soirées vs concerts) restent mélangées car elles partagent de la variance globale (flou, éclairage artificiel, groupes de personnes).

**KMeans** suppose des clusters sphériques et équilibrés, avec un `k` fixé à l'avance. Sur des embeddings CLIP L2-normalisés qui forment des structures non-sphériques sur une hypersphère, KMeans est structurellement inadapté.

**k=5 est trop faible** pour la diversité réelle des photos (soirées, concerts, selfies, paysages, nourriture, voitures, famille, sport...) — des catégories très différentes s'agrègent en un seul cluster fourre-tout.

---

## Clustering — V2 : UMAP + HDBSCAN ✅

### Config Spark (`02_clip_clustering`)

```python
spark.driver.memory          = "4g"
spark.sql.shuffle.partitions = "8"
```

UMAP et HDBSCAN tournent entièrement sur le **driver en numpy** — Spark sert uniquement à lire le Parquet et à sauvegarder le résultat. Les 4g sont suffisants pour les embeddings (7 Mo) et les structures intermédiaires UMAP/HDBSCAN (~50 Mo).

### Pourquoi UMAP

UMAP (Uniform Manifold Approximation and Projection) est une réduction **non-linéaire** qui préserve la structure locale et globale du manifold. Sur des embeddings CLIP (distribution sur une hypersphère), UMAP avec `metric="cosine"` respecte la géométrie naturelle des embeddings — deux photos similaires restent proches après réduction.

| | PCA | UMAP |
|---|---|---|
| Type | Linéaire | Non-linéaire |
| Structure préservée | Variance globale | Voisinage local + global |
| Métrique | Euclidienne | Cosine (paramétrable) |
| Adapté aux hypersphères | Non | Oui |

### Paramètres UMAP

```python
umap.UMAP(n_components=50, n_neighbors=15, min_dist=0.1, metric='cosine')
```

| Paramètre | Valeur | Justification |
|---|---|---|
| `n_components` | 50 | Espace intermédiaire pour HDBSCAN. 768D→50D réduit le bruit dimensionnel sans écraser la structure locale. Trop bas (2D) = perte d'info pour le clustering ; trop haut (200D) = malédiction de la dimensionnalité pour HDBSCAN. |
| `n_neighbors` | 15 | Taille du voisinage local pour construire le graphe de similarité. Petit (5) = structure fine, sensible au bruit. Grand (50) = structure globale, clusters larges. 15 est le défaut UMAP, bon équilibre sur ~2400 points. |
| `min_dist` | 0.1 | Distance minimale entre points dans l'espace réduit. 0.0 = clusters très compressés. 1.0 = distribution uniforme, structure locale perdue. 0.1 préserve la structure sans sur-comprimer. |
| `metric` | `cosine` | Distance dans l'espace original (768D). Embeddings L2-normalisés → cosine distance ≡ euclidienne sur l'hypersphère, mais utiliser `cosine` explicitement est plus correct. |

Un deuxième UMAP 2D (mêmes paramètres) est calculé séparément pour la **visualisation dashboard** — les 2D de visualisation ne sont pas utilisées pour HDBSCAN car trop compressées.

### Pourquoi HDBSCAN

HDBSCAN (Hierarchical Density-Based Spatial Clustering) ne requiert pas de `k` fixé. Il trouve des clusters de **densité arbitraire**, et marque les points isolés comme bruit (`-1`) plutôt que de les forcer dans un cluster. Le cluster fourre-tout de V1 devient du bruit structuré — ce qui est honnête sur les photos sans thème dominant.

| | KMeans | HDBSCAN |
|---|---|---|
| k fixé | Oui | Non |
| Forme des clusters | Sphérique | Arbitraire |
| Outliers | Forcés dans un cluster | Marqués -1 |
| Adapté aux embeddings | Non | Oui |

### Paramètres HDBSCAN

```python
hdbscan.HDBSCAN(min_cluster_size=50, min_samples=5, metric='euclidean', cluster_selection_method='eom')
```

| Paramètre | Valeur | Justification |
|---|---|---|
| `min_cluster_size` | 50 | Taille minimale d'un cluster (≈ 2% des 2419 photos). Trop petit (10) → micro-clusters parasites, testé avec 30 : trop fragmenté. Trop grand (200) → clusters fusionnés. |
| `min_samples` | 5 | Nombre de voisins requis pour qu'un point soit "core point". Petit (1) = moins de bruit. Grand (20) = clusters plus denses, plus de photos classées bruit. 5 : compromis — les photos atypiques vont en bruit sans sur-peupler le cluster -1. |
| `metric` | `euclidean` | Distance sur l'espace UMAP 50D. UMAP produit des coordonnées cartésiennes (pas des embeddings normalisés) → euclidean est correct ici, contrairement à la métrique cosine utilisée dans UMAP. |
| `cluster_selection_method` | `eom` | Excess of Mass — favorise les clusters stables de tailles inégales (réaliste : soirées = 1295 photos vs enfance = 67). L'alternative `leaf` donnerait des clusters plus petits et équilibrés, moins adaptée à ce corpus. |

### Labelling automatique → abandonné, labels manuels

L'auto-labeling CLIP texte a été tenté mais abandonné : les sous-catégories de "photos sociales" (soirées, quotidien entre amis, amis en voyage, enfance) sont trop proches sémantiquement dans l'espace CLIP — tous les clusters sociaux recevaient le même label quel que soit `CANDIDATE_LABELS`.

**Solution retenue** : inspection visuelle des clusters dans le dashboard → labels manuels hardcodés :

```python
cluster_labels = {
    -1: "photos diverses",
     0: "photos d'enfance",
     1: "amis en voyage",
     2: "memes et humour",
     3: "quotidien entre amis",
     4: "photos diverses",
     5: "soirees",
}
```

---

## Erreurs rencontrées et solutions

| Erreur | Cause | Solution |
|---|---|---|
| `AttributeError: 'BaseModelOutputWithPooling' has no attribute 'norm'` (images) | `CLIPModel.get_image_features()` retourne un objet selon la version transformers | Utiliser `CLIPVisionModelWithProjection` → `.image_embeds` |
| `AttributeError: 'BaseModelOutputWithPooling' has no attribute 'norm'` (texte) | `CLIPModel.get_text_features()` même problème | Utiliser `CLIPTextModelWithProjection` → `.text_embeds` |
| `AnalysisException: Can't extract value from pca_coords` | MLlib Vector est un STRUCT, pas un ARRAY — `.getItem()` échoue | `vector_to_array(F.col("pca_coords"))` avant `.getItem()` |
| `AttributeError: 'numpy.ndarray' has no attribute 'toArray'` | `km_model.clusterCenters()` retourne déjà des numpy arrays | `np.array(km_model.clusterCenters())` directement |
| `ValueError: matmul dimension mismatch (768 vs 50)` | Centroïdes en 50D (PCA), embeddings texte en 768D | Projection numpy via `pca50_model.pc.toArray()` (matrice 768×50) |
| `ModuleNotFoundError: No module named 'torch'` | torch absent du Docker image de base | Couche `pyspark-clip` dans Dockerfile avec index CPU-only |
| Silhouette 0.019 avec StandardScaler | StandardScaler détruit la normalisation L2 des embeddings CLIP | Supprimer StandardScaler, les embeddings sont déjà normalisés |

---

## Résultats V2 — inspection visuelle

| Cluster | Label retenu | Réalité | Qualité |
|---|---|---|---|
| -1 | photos diverses | mix soirées, plats, portraits, paysages, voitures | ✅ honnête |
| 0 | photos d'enfance | photos de moi et mes potes enfants | ✅ propre |
| 1 | amis en voyage | amis en voyage | ✅ bien identifié |
| 2 | memes et humour | memes | ✅ parfait |
| 3 | quotidien entre amis | photos du quotidien entre amis | ✅ nickel |
| 4 | photos diverses | fourre-tout : amis, voyage, enfance mélangés | ⚠️ acceptable |
| 5 | soirees | photos de soirées | ✅ parfait |

**323 photos en bruit (13.4%)** — pas du vrai bruit, photos trop diverses pour appartenir à un cluster dense.

---

## Limites et comparaison avec Apple Photos

Apple Photos obtient de meilleurs résultats car ils combinent plusieurs signaux absents ici :

| Signal | Apple Photos | Ce projet |
|---|---|---|
| Métadonnées GPS + date | ✅ principal signal | ❌ absent (export Instagram) |
| Reconnaissance de visages | ✅ clustering par personne | ❌ non implémenté |
| Classification de scènes fine-tunée | ✅ modèles dédiés par catégorie | ⚠️ CLIP généraliste |
| Embeddings visuels | ✅ | ✅ CLIP ViT-L/14 |

**Amélioration possible** : clustering de visages (`InsightFace` ou `face_recognition`) pour séparer "photos avec tes potes" / "photos famille" / "selfies seul" — orthogonal au clustering visuel actuel.

---

## Dashboard — `/photos`

- Scatter interactif UMAP 2D coloré par cluster
- Chips de sélection par cluster → grille complète de toutes les photos du cluster
- Route Flask `/photo/<path>` pour servir les images depuis `data/raw/INSTAGRAM/`
- Chemins Spark (`/opt/spark/data/...`) réécrits automatiquement en chemins dashboard (`/app/data/...`)
