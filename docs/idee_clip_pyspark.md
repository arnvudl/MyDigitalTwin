# Idée — Deep Learning visuel avec CLIP + PySpark

## Concept

Utiliser le modèle **CLIP** (OpenAI, via Hugging Face) pour générer des embeddings
visuels à partir des photos Instagram, puis exploiter ces embeddings dans PySpark
pour le clustering K-Means (axe 3 du plan ML).

Le Deep Learning génère les features → PySpark fait le ML.  
Les deux technologies se complètent et sont toutes deux justifiées dans le rapport.

---

## Pipeline prévu

```
data/raw/INSTAGRAM/media/
        ↓
CLIP sur RTX 4090 (Python + PyTorch)
        ↓
embeddings.parquet  (1 vecteur de 768 dims par photo)
        ↓
K-Means PySpark sur les embeddings
        ↓
Clusters thématiques : concerts, soirées, voyages, food...
```

---

## Stack technique

| Composant | Outil |
|---|---|
| Modèle | `openai/clip-vit-large-patch14` |
| Framework | Hugging Face `transformers` + PyTorch |
| GPU | RTX 4090 Studio (24 Go VRAM) |
| Batch size | ~128 images à la fois (à ajuster) |
| Output | Parquet — 1 ligne par photo, vecteur de 768 dimensions |
| ML | K-Means PySpark sur les embeddings |

---

## Code de départ (à compléter plus tard)

```python
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import torch
import os

# Charger le modèle sur GPU
model     = CLIPModel.from_pretrained("openai/clip-vit-large-patch14").to("cuda")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
model.eval()

# Scanner les photos Instagram
photo_dir = "data/raw/INSTAGRAM/media"
photos    = [f for f in os.listdir(photo_dir) if f.endswith((".jpg", ".jpeg", ".png"))]

# Générer les embeddings en batch
embeddings = []
batch_size = 128

with torch.no_grad():
    for i in range(0, len(photos), batch_size):
        batch = photos[i:i+batch_size]
        images = [Image.open(os.path.join(photo_dir, f)).convert("RGB") for f in batch]
        inputs = processor(images=images, return_tensors="pt").to("cuda")
        feats  = model.get_image_features(**inputs)
        feats  = feats / feats.norm(dim=-1, keepdim=True)  # normalisation L2
        embeddings.extend(feats.cpu().numpy().tolist())

# → sauvegarder en Parquet avec PySpark
```

---

## Ce que ça apporte au projet

- **Axe 3 (K-Means)** : clustering sémantique des photos plutôt que features manuelles
- **Rapport** : justifie l'usage de deux technologies complémentaires (DL + Big Data)
- **Originalité** : peu de projets académiques combinent CLIP et PySpark

---

## Quand l'implémenter ?

**Pas maintenant.** À intégrer lors de l'étape **Data Engineering (remise 10 mai)**,
une fois que tous les notebooks texte sont terminés et que le pipeline Parquet est stable.

---

*Note créée le 28/03/2026 — à rappeler lors de l'étape Data Engineering*
