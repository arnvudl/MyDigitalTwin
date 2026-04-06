# AXE 4 — Clustering Photo avec CLIP
_Priorité : basse — après remise Data Engineering (10 mai)_

---

## Objectif

Regrouper automatiquement tes photos Instagram en **clusters thématiques** sans labels manuels : soirées, concerts, voyages, food, sport…

---

## Pourquoi CLIP ?

CLIP (OpenAI) est un modèle multimodal entraîné sur des millions de paires image-texte.  
Il génère un **embedding de 768 dimensions** qui capture le contenu sémantique d'une image.  
Deux photos "concert" auront des embeddings proches, même si elles sont visuellement différentes.

**Avantage** : zéro annotation manuelle, zéro dataset d'entraînement personnel.

---

## Stack technique

| Composant | Outil |
|---|---|
| Modèle | `openai/clip-vit-large-patch14` (Hugging Face) |
| Framework | PyTorch + `transformers` |
| Batch size | ~128 images (ajustable selon VRAM disponible) |
| Clustering | K-Means PySpark sur les embeddings |
| Output | `warehouse/photo_embeddings.parquet` + `warehouse/photo_clusters.parquet` |

---

## Pipeline

```
data/raw/INSTAGRAM/media/  (photos .jpg/.jpeg/.png)
        ↓
01_clip_embeddings.py  (Python pur, GPU)
  - CLIPModel + CLIPProcessor sur GPU
  - Batch de 128 images → vecteur 768 dims par photo
  - Export : warehouse/photo_embeddings.parquet
        ↓
02_photo_clustering.ipynb  (PySpark)
  - Lecture embeddings
  - KMeans(k=8, seed=42) sur vecteurs CLIP
  - PCA 2D pour visualisation
  - Export : warehouse/photo_clusters.parquet
        ↓
app/pages/photos.py
  - Grille de photos par cluster
  - Label automatique du cluster (top CLIP text similarity)
```

---

## Labelling automatique des clusters

CLIP peut aussi comparer une image à des textes.  
Pour labeliser un cluster, on compare son centroïde à une liste de textes candidats :

```python
candidate_labels = [
    "concert", "soirée entre amis", "voyage", "nourriture",
    "sport", "famille", "gaming setup", "nature", "ville"
]
# → le label avec le score cosine le plus élevé gagne
```

---

## Dashboard — page `/photos`

- Grille de photos groupées par cluster thématique
- Titre du cluster généré automatiquement (CLIP text similarity)
- Clic sur un cluster → zoom sur les photos
- Timeline : "ta vie en photos par période"

---

## Contraintes

- Photos Instagram dans `data/raw/INSTAGRAM/media/` (gitignore — données personnelles)
- Traitement GPU uniquement pour les embeddings (CPU trop lent sur 1000+ photos)
- Embeddings = 768 floats × N photos → taille raisonnable en Parquet

---

## Timing

**Ne pas implémenter avant le 10 mai** (remise Data Engineering).  
Pré-requis :
1. ✅ Pipeline PySpark stable (clustering comportemental terminé)
2. ⏳ Notebooks ALS + Clone terminés
3. ⏳ Vérifier disponibilité des photos dans `data/raw/INSTAGRAM/media/`
