# Phase 07 — Topologie des Données Personnelles (Shape of Me)

_Dossier_ : `src/scripts/07_topology/`  
_Statut_ : À implémenter  
_Notebooks_ : `01_embed_sources.ipynb`, `02_mapper_views.ipynb`, `03_export_dashboard.ipynb`  
_Outputs_ : `data/warehouse/topology/{source}_{filter}.parquet`  
_Inspiré par_ : [tda-mapper-python](https://github.com/lucasimi/tda-mapper-python) + projet X bookmarks (TDA sur embeddings personnels)

---

## Contexte & Motivation

### Ce que fait le projet de référence

Un utilisateur Twitter/X a cartographié la **forme** de ses bookmarks en appliquant TDA Mapper sur des embeddings de texte, puis généré 3 vues différentes du même graphe :

- **density** : où gravite l'attention (zones denses = intérêts récurrents)
- **PCA** : les axes de variation dominants (qu'est-ce qui varie le plus dans tes contenus ?)
- **centroid** : centre vs périphérie (typique → outlier)

La clé : ce n'est pas 3 algorithmes différents. C'est **le même graphe Mapper, vu à travers 3 fonctions de filtre différentes**. Le filtre change la "lentille" sans reconstruire la structure.

### Pourquoi c'est intéressant dans MyDigitalTwin

La Phase 02 produit du **clustering étanche** : K-Means force chaque événement dans exactement 1 cluster. C'est une contrainte artificielle.

TDA Mapper produit des **clusters chevauchants** : une écoute Spotify un vendredi soir peut appartenir à la fois au cluster "soirée connectée" et au cluster "Spotify journée" — ce qui est vrai dans la réalité. Un artiste peut vivre à cheval entre deux genres.

De plus, Mapper détecte des **structures topologiques** invisibles au clustering classique :
- Des **trous** (zones jamais explorées dans ton espace d'écoute)
- Des **ponts** (éléments qui connectent deux communautés sans appartenir à aucune)
- Des **branches** (évolutions temporelles de tes goûts)

---

## Architecture — Le module "Shape of Me"

Le principe de modularité : un seul pipeline paramétrable qui accepte n'importe quelle source du warehouse.

```
Source warehouse
    ↓
EmbedderStrategy (swappable selon la source)
    ↓
TDA Mapper (tda-mapper-python)
    avec filtre F₁ → topology/{source}_density.parquet
    avec filtre F₂ → topology/{source}_pca.parquet
    avec filtre F₃ → topology/{source}_centroid.parquet
    ↓
Dashboard /topology
    3d-force-graph.js (même rendu que /social)
    sélecteur source + filtre dans la sidebar
```

### Sources candidates

| Source | Table warehouse | Embedder à utiliser | Question révélée |
|---|---|---|---|
| `spotify_streams` | `spotify_streams` | sentence-transformers sur `trackName + artistName` | Quel est le centre de gravité musical ? Quels genres sont des outliers ? |
| `youtube_watch` | `youtube_watch` | sentence-transformers sur `title` | Où va vraiment ton attention sur YouTube ? |
| `behavioral_clusters` | `behavioral_clusters` | features numériques brutes (hour, weekday, platform OHE) | Quelle est la vraie forme de tes habitudes temporelles ? |
| `photo_clusters` | `photo_embeddings` | vecteurs CLIP déjà calculés (768D) | Quelles photos chevauchent plusieurs thèmes ? |
| `social_graph` | `social_graph` | features de graphe (degree, betweenness, weight) | Qui est vraiment un pont entre tes communautés ? |
| `netflix_views` | `netflix_views` | vecteurs ALS déjà calculés (rank 20) | Quels films/séries sont outliers dans tes goûts ? |

---

## Implémentation

### Dépendances

```bash
pip install tda-mapper-python sentence-transformers umap-learn numpy pandas pyarrow
```

`tda-mapper-python` est la lib de référence (repo : `lucasimi/tda-mapper-python`). Elle implémente l'algorithme Mapper de façon simple et efficace sans dépendances lourdes.

### Notebook 01 — `01_embed_sources.ipynb`

Objectif : produire un vecteur par item pour chaque source, et le sauvegarder dans le warehouse.

```python
from sentence_transformers import SentenceTransformer
import pandas as pd
import numpy as np
from sklearn.preprocessing import normalize

model = SentenceTransformer("all-MiniLM-L6-v2")  # 384D, rapide, bon compromis

# --- Spotify ---
df = pd.read_parquet("data/warehouse/spotify_streams/")
texts = (df["trackName"] + " " + df["artistName"]).tolist()
embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)
embeddings = normalize(embeddings)  # L2 normalisation — obligatoire pour cosine

np.save("data/warehouse/topology/spotify_embeddings.npy", embeddings)
df[["trackName", "artistName", "event_hour", "event_weekday"]].to_parquet(
    "data/warehouse/topology/spotify_meta.parquet"
)

# --- Photos (CLIP déjà calculé — réutiliser directement) ---
# Les embeddings CLIP sont dans data/warehouse/photo_embeddings/
# Pas besoin de recalculer — c'est l'avantage d'avoir tout dans le warehouse
photo_df = pd.read_parquet("data/warehouse/photo_embeddings/")
embeddings_clip = np.stack(photo_df["embedding"].values)
embeddings_clip = normalize(embeddings_clip)
np.save("data/warehouse/topology/photo_embeddings.npy", embeddings_clip)
```

> **Note sur le choix du modèle** : `all-MiniLM-L6-v2` (384D) est suffisant pour Spotify/YouTube où les textes sont courts (titres). Pour le clone ou des corpus plus riches, utiliser `all-mpnet-base-v2` (768D, même dimension que CLIP). Ne pas mélanger les dimensions entre sources.

### Notebook 02 — `02_mapper_views.ipynb`

C'est le cœur. Même code, 3 filtres différents.

```python
import numpy as np
import pandas as pd
from tdamapper.core import MapperAlgorithm
from tdamapper.cover import CubicalCover
from tdamapper.clustering import TrivialClustering
from sklearn.decomposition import PCA
from sklearn.neighbors import KernelDensity
import networkx as nx

# Charger les embeddings
source = "spotify"  # paramètre swappable
X = np.load(f"data/warehouse/topology/{source}_embeddings.npy")
meta = pd.read_parquet(f"data/warehouse/topology/{source}_meta.parquet")

# --- Réduction dimensionnelle préalable (UMAP 50D → Mapper) ---
# Même logique que Phase 05 CLIP : UMAP préserve la structure locale mieux que PCA
import umap
reducer = umap.UMAP(n_components=50, n_neighbors=15, min_dist=0.1, metric="cosine")
X_reduced = reducer.fit_transform(X)

# --- Les 3 filtres ---

# Filtre 1 : Density (estimation de densité kernel)
kde = KernelDensity(kernel="gaussian", bandwidth=0.5).fit(X_reduced)
lens_density = kde.score_samples(X_reduced).reshape(-1, 1)

# Filtre 2 : PCA (1er composante principale = axe de variation max)
pca = PCA(n_components=1)
lens_pca = pca.fit_transform(X_reduced)

# Filtre 3 : Centroid distance (distance euclidienne au centroïde global)
centroid = X_reduced.mean(axis=0)
lens_centroid = np.linalg.norm(X_reduced - centroid, axis=1).reshape(-1, 1)

# --- Mapper avec chaque filtre ---
def run_mapper(X, lens, n_intervals=10, overlap=0.3):
    """
    n_intervals : nb de découpes de l'espace filtre
                  Plus grand = graphe plus fin, plus de nœuds
    overlap     : chevauchement entre intervalles (0.3 = 30%)
                  C'est ce qui crée les chevauchements de clusters
                  Plus grand = plus de connexions, graphe plus dense
    """
    cover = CubicalCover(n_intervals=n_intervals, overlap_frac=overlap)
    clustering = TrivialClustering()  # ou DBSCAN pour sous-clustering
    mapper = MapperAlgorithm(cover=cover, clustering=clustering)
    graph = mapper.fit_transform(X, lens)
    return graph

graph_density  = run_mapper(X_reduced, lens_density)
graph_pca      = run_mapper(X_reduced, lens_pca)
graph_centroid = run_mapper(X_reduced, lens_centroid)

# --- Export pour le dashboard ---
def graph_to_parquet(graph, meta, lens_values, source, filter_name):
    """Convertit le graphe Mapper en format nodes+edges pour 3d-force-graph"""
    nodes = []
    for node_id, point_ids in graph.nodes(data="data"):
        # Chaque nœud Mapper = un groupe de points originaux
        node_meta = meta.iloc[list(point_ids)]
        nodes.append({
            "id": str(node_id),
            "size": len(point_ids),
            "label": node_meta.iloc[0].get("trackName", str(node_id)),  # label du point central
            "avg_lens": float(lens_values[list(point_ids)].mean()),
            "items": list(point_ids),  # points originaux dans ce nœud
        })

    edges = []
    for u, v in graph.edges():
        # Chevauchement = nb de points partagés entre 2 nœuds
        shared = len(set(graph.nodes[u]["data"]) & set(graph.nodes[v]["data"]))
        edges.append({"source": str(u), "target": str(v), "weight": shared})

    pd.DataFrame(nodes).to_parquet(
        f"data/warehouse/topology/{source}_{filter_name}_nodes.parquet"
    )
    pd.DataFrame(edges).to_parquet(
        f"data/warehouse/topology/{source}_{filter_name}_edges.parquet"
    )

graph_to_parquet(graph_density,  meta, lens_density,  source, "density")
graph_to_parquet(graph_pca,      meta, lens_pca,      source, "pca")
graph_to_parquet(graph_centroid, meta, lens_centroid, source, "centroid")
```

> **Paramètres clés à calibrer par source** :
> - `n_intervals` : 8-10 pour Spotify (beaucoup de points), 5-7 pour Photos (moins de points)
> - `overlap_frac` : 0.3 est le défaut raisonnable. Descendre à 0.2 pour moins de connexions, monter à 0.5 pour un graphe plus connecté
> - `bandwidth` KDE : à ajuster selon la densité des embeddings — si le graphe est trop fragmenté, augmenter

### Notebook 03 — `03_export_dashboard.ipynb`

Génère le JSON final pour le dashboard, avec enrichissement des nœuds.

```python
import json

def build_graph_json(source, filter_name, color_by="size"):
    nodes_df = pd.read_parquet(f"data/warehouse/topology/{source}_{filter_name}_nodes.parquet")
    edges_df = pd.read_parquet(f"data/warehouse/topology/{source}_{filter_name}_edges.parquet")
    meta = pd.read_parquet(f"data/warehouse/topology/{source}_meta.parquet")

    # Normalisation taille → val pour 3d-force-graph (même pattern que /social)
    max_size = nodes_df["size"].max()
    nodes_df["val"] = (5 + 45 * nodes_df["size"] / max_size).astype(int)

    # Couleur par avg_lens (gradient chaud → froid selon la valeur du filtre)
    # density haute = rouge (zone dense = attentionnée)
    # centroid élevé = bleu (outlier)
    nodes_json = nodes_df[["id", "label", "val", "avg_lens", "size"]].to_dict("records")
    edges_json = edges_df[["source", "target", "weight"]].to_dict("records")

    return {"nodes": nodes_json, "links": edges_json}

# Écrire tous les JSONs
for source in ["spotify", "photo", "social"]:
    for filter_name in ["density", "pca", "centroid"]:
        data = build_graph_json(source, filter_name)
        with open(f"app/assets/topology_{source}_{filter_name}.json", "w") as f:
            json.dump(data, f)
```

---

## Dashboard — Page `/topology`

### Structure de la page (Dash)

```python
# app/pages/topology.py

import dash
from dash import dcc, html, Input, Output, callback
import json

dash.register_page(__name__, path="/topology", name="Topology")

SOURCES = {
    "spotify": "Spotify — écoutes",
    "photo": "Photos — CLIP",
    "social": "Réseau social",
}
FILTERS = {
    "density": "Densité — où gravite l'attention",
    "pca": "PCA — axes de variation dominants",
    "centroid": "Centroïde — typique vs outlier",
}

def layout():
    return html.Div([
        html.Div([
            # Sidebar contrôles
            dcc.Dropdown(
                id="topo-source",
                options=[{"label": v, "value": k} for k, v in SOURCES.items()],
                value="spotify",
                clearable=False,
            ),
            dcc.RadioItems(
                id="topo-filter",
                options=[{"label": v, "value": k} for k, v in FILTERS.items()],
                value="density",
            ),
        ], style={"width": "280px", "padding": "20px"}),

        # Graphe 3D (même iframe pattern que /social)
        html.Iframe(
            id="topo-graph",
            src="/assets/topology_spotify_density.html",
            style={"flex": 1, "height": "80vh", "border": "none"},
        ),
    ], style={"display": "flex"})

@callback(
    Output("topo-graph", "src"),
    Input("topo-source", "value"),
    Input("topo-filter", "value"),
)
def update_graph(source, filter_name):
    # Régénérer le HTML avec les nouvelles données
    _build_3d_html(source, filter_name)
    return f"/assets/topology_{source}_{filter_name}.html"
```

### Rendu 3D (même pattern que `/social`)

Réutiliser exactement `_build_3d_html()` de `06_social`. La seule différence : les nœuds sont colorés par `avg_lens` (valeur du filtre) au lieu du statut "close friend".

```javascript
// Dans le HTML généré, coloration par avg_lens
node.color = lensToColor(node.avg_lens);  // gradient chaud → froid

function lensToColor(val) {
    // density haute = amber (attention concentrée)
    // density basse = teal (périphérie)
    const t = (val - minLens) / (maxLens - minLens);
    return t > 0.5 ? '#EF9F27' : '#1D9E75';
}
```

---

## Différence fondamentale avec la Phase 02

| | Phase 02 — K-Means | Phase 07 — TDA Mapper |
|---|---|---|
| Clusters | Étanches (1 point = 1 cluster) | Chevauchants (1 point peut être dans N clusters) |
| k | Fixé à 6 avant l'algo | Émergent de la structure des données |
| Outliers | Forcés dans le cluster le plus proche | Visibles comme nœuds isolés ou petits |
| Évolution temporelle | Ignorée | Capturée si on encode le temps dans le filtre |
| Interprétation | Statistique (silhouette score) | Topologique (connectivité, trous, branches) |

Le cas concret le plus parlant sur Spotify : un artiste comme Frank Ocean peut appartenir à la fois au cluster "R&B introspectif" et au cluster "indie expérimental" dans Mapper — là où K-Means le forçait dans l'un ou l'autre. Ce nœud chevauchant apparaît visuellement comme un **pont** dans le graphe.

---

## Calibration et points d'attention

### Choisir `n_intervals` et `overlap_frac`

```
Trop peu d'intervalles  → graphe trop simple, perd la structure fine
Trop d'intervalles      → graphe fragmenté, trop de nœuds isolés
Trop peu de chevauchement → graphe déconnecté
Trop de chevauchement   → graphe trop dense, illisible
```

Recette pratique :
1. Commencer avec `n_intervals=8, overlap_frac=0.3`
2. Si le graphe est déconnecté → augmenter `overlap_frac` à 0.4
3. Si le graphe est une boule compacte → réduire `overlap_frac` à 0.25
4. Ajuster `n_intervals` pour avoir entre 15 et 50 nœuds (lisible dans 3d-force-graph)

### Encodage temporel (bonus pour Spotify)

Pour détecter les évolutions de goûts dans le temps, utiliser un filtre temporel :

```python
# Filtre 4 : temps (date d'écoute normalisée)
lens_time = (df["ts"].astype("int64") - df["ts"].astype("int64").min())
lens_time = (lens_time / lens_time.max()).values.reshape(-1, 1)
graph_time = run_mapper(X_reduced, lens_time)
```

Ce filtre fait apparaître l'**évolution chronologique** de tes goûts comme une trajectoire dans le graphe — les nœuds du passé d'un côté, le présent de l'autre, les éventuels retours visibles comme des boucles.

### Pièges à éviter

**Ne pas StandardScaler les embeddings CLIP/sentence-transformers** : ces vecteurs sont déjà L2-normalisés. Un StandardScaler détruirait la normalisation (même erreur que Phase 05 avec Silhouette à 0.019).

**Réduire en 50D avant Mapper, pas en 2D** : une réduction 2D pour la visualisation est différente de la réduction pour Mapper. Mapper travaille mieux sur 50D (moins de perte d'information) — le 2D ne sert qu'à afficher.

**TikTok : limiter à 2000 samples** comme en Phase 02 — 234k points créeraient un graphe Mapper avec des milliers de nœuds, illisible.

---

## Résultats attendus

### Ce qu'on verra sur Spotify

- **Vue density** : les artistes/genres les plus écoutés formeront des nœuds larges au centre. Les écoutes rares seront en périphérie. Révèle le vrai "centre de gravité" musical sans biais de comptage.
- **Vue PCA** : le graphe s'étirera le long du premier axe de variation — probablement énergie vs mélancolie, ou électronique vs acoustique selon tes goûts.
- **Vue centroid** : les écoutes "typiques d'Arnaud" au centre, les explorations atypiques repoussées en périphérie. Les outliers sont souvent les découvertes les plus intéressantes.

### Ce qu'on verra sur les photos

Les 323 photos que HDBSCAN classait comme bruit (-1) en Phase 05 ne disparaissent plus — elles deviennent des **nœuds pont** entre deux clusters dans Mapper. Ce qui était du "bruit" pour HDBSCAN est de l'**information topologique** pour Mapper.

### Ce qu'on verra sur le graphe social

Les contacts qui "font le pont" entre deux groupes d'amis apparaissent explicitement comme des nœuds à forte betweenness dans le graphe Mapper — une information que le graphe `/social` actuel montre qualitativement mais que Mapper formalise.

---

## Fichiers à créer

```
src/scripts/07_topology/
├── 01_embed_sources.ipynb
├── 02_mapper_views.ipynb
└── 03_export_dashboard.ipynb

data/warehouse/topology/
├── spotify_embeddings.npy
├── spotify_meta.parquet
├── spotify_density_nodes.parquet
├── spotify_density_edges.parquet
├── spotify_pca_nodes.parquet
├── spotify_pca_edges.parquet
├── spotify_centroid_nodes.parquet
└── spotify_centroid_edges.parquet
(idem pour photo, social, ...)

app/pages/topology.py
app/assets/topology_*.html  ← générés dynamiquement
```

---

## Références

- [tda-mapper-python](https://github.com/lucasimi/tda-mapper-python) — lib Mapper utilisée
- [Article original Mapper — Singh, Mémoli, Carlsson (2007)](https://research.math.osu.edu/tgda/mapperPaper.pdf)
- [UMAP documentation](https://umap-learn.readthedocs.io/) — réduction dimensionnelle préalable
- [sentence-transformers](https://www.sbert.net/) — embeddings texte
- Phase 05 (`05_clip.md`) — pattern UMAP+HDBSCAN réutilisé ici
- Phase 06 (`06_social.md`) — pattern 3d-force-graph.js réutilisé ici
