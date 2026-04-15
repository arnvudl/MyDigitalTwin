# Phase 05 — Clustering Photos CLIP

_Dossier_ : `src/scripts/05_CLIP/`  
_Statut_ : ✅ Terminé (V1 PCA+KMeans → V2 UMAP+HDBSCAN, labels manuels)  
_Dernière mise à jour_ : 2026-04-15

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
    Labelling : CLIPTextModelWithProjection sur centroïdes → text similarity
    → data/warehouse/photo_clusters/ (Parquet)
    ↓
Dashboard /photos
    Scatter UMAP 2D interactif, galerie filtrée par cluster
```

---

## Embeddings — `01_clip_embeddings.ipynb`

- **Input** : `data/raw/INSTAGRAM/CLIP_SORTING/` — 2 419 photos triées manuellement
- **Modèle** : `CLIPVisionModelWithProjection` + `CLIPImageProcessor`
- **Spark** : `mapInPandas` — exception justifiée à la règle no-UDF : le modèle PyTorch doit être chargé une fois par partition en Python pur, sans équivalent JVM
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

### Pourquoi UMAP

UMAP (Uniform Manifold Approximation and Projection) est une réduction **non-linéaire** qui préserve la structure locale et globale du manifold. Sur des embeddings CLIP (distribuition sur une hypersphère), UMAP avec `metric="cosine"` respecte la géométrie naturelle des embeddings — deux photos similaires restent proches après réduction.

Comparaison directe :

| | PCA | UMAP |
|---|---|---|
| Type | Linéaire | Non-linéaire |
| Structure préservée | Variance globale | Voisinage local + global |
| Métrique | Euclidienne | Cosine (paramétrable) |
| Adapté aux hypersphères | Non | Oui |

### Pourquoi HDBSCAN

HDBSCAN (Hierarchical Density-Based Spatial Clustering) ne requiert pas de `k` fixé. Il trouve des clusters de **densité arbitraire**, et marque les points isolés comme bruit (`-1`) plutôt que de les forcer dans un cluster. Le cluster fourre-tout de V1 devient du bruit structuré — ce qui est honnête sur les photos sans thème dominant.

| | KMeans | HDBSCAN |
|---|---|---|
| k fixé | Oui | Non |
| Forme des clusters | Sphérique | Arbitraire |
| Outliers | Forcés dans un cluster | Marqués -1 |
| Adapté aux embeddings | Non | Oui |

### Paramètres retenus

```python
umap.UMAP(n_components=50, n_neighbors=15, min_dist=0.1, metric="cosine")
hdbscan.HDBSCAN(min_cluster_size=30, min_samples=5, metric="euclidean")
```

- `n_components=50` : espace intermédiaire avant HDBSCAN (compromis qualité/vitesse)
- `min_cluster_size=30` : évite les micro-clusters parasites sur 2 419 photos
- `metric="cosine"` dans UMAP car embeddings L2-normalisés → distance cosine = distance euclidienne, mais expliciter la métrique améliore la qualité

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
