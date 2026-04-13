# Phase 05 — Clustering Photos CLIP

_Dossier_ : `src/scripts/05_CLIP/`  
_Statut_ : ⏳ Non commencé (prévu avant le 19 avril)  
_Plan_ : `src/scripts/05_CLIP/PLAN.md`

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
- Compatible avec une inférence locale sur GPU 8Go (quantification possible).

---

## Architecture prévue

```
photos Instagram (JPG)
    ↓
CLIP encoder (Python local)   →   embeddings 768-dim par photo
    ↓
PySpark DataFrame (embeddings)
    ↓
K-Means Spark ML (k à déterminer)   →   cluster_id par photo
    ↓
Labelling automatique (CLIP text similarity sur centroïdes)
    ↓
data/warehouse/photo_clusters.parquet
    ↓
Dashboard /photos (galerie filtrée par cluster)
```

### Pourquoi K-Means sur Spark pour les embeddings ?

Les photos Instagram peuvent représenter plusieurs milliers d'images. Bien que K-Means scikit-learn serait suffisant pour ce volume, utiliser **Spark ML** maintient la cohérence du pipeline : le même `KMeans` et `VectorAssembler` que dans la phase 02, le résultat écrit dans le même warehouse.

---

## Ce qui reste à faire

- [ ] Écrire le script d'extraction CLIP (`01_clip_embeddings.py`)
- [ ] Déterminer k via Silhouette Score sur un échantillon de photos
- [ ] Labelliser les clusters via text similarity
- [ ] Écrire dans `data/warehouse/photo_clusters.parquet`
- [ ] Créer la page `/photos` dans le dashboard
