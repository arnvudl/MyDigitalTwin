# Checkpoint — K-Means Clustering
_Dernière mise à jour : 2026-04-05_

---

## État actuel

### ✅ PARTIE A — Content Clustering (terminée, résultats archivés)

**Notebook** : `01_content_clustering.ipynb`

**Résultat** : K-Means k=15 tourne mais produit un cluster catch-all dominant (~73% des données).
Décision : **ne pas utiliser le content clustering pour la home page**.
Les labels sont sauvegardés dans A5 pour référence future.

**Pourquoi ça ne marche pas bien** :
- TF-IDF sur textes courts multi-sources (Spotify artistes, Google searches, titres YouTube) = clusters mal séparés
- Silhouette ~0.19, cluster 0 = fourre-tout structurel

**Stratégie révisée pour la home page** :
- Garder `CATEGORY_KEYWORDS` dans `home.py`
- Enrichir les scores avec les vraies données Delta (compter les occurrences dans `google_searches`, `youtube_watch`, `google_chrome`, `spotify_streams`, `netflix_views`)
- → Score de "⚽ Sport" = nb de fois où "football/nba/..." apparaît dans les vraies recherches

---

### ⏳ PARTIE B — Behavioral Clustering (à faire)

**Notebook** : `02_behavioral_clustering.ipynb`

**Avant de lancer B1**, vérifier les volumes :
```python
print("TikTok:", read_table("tiktok_watch").count())
print("Instagram:", read_table("instagram_likes").count())
```
Si l'un dépasse ~3000-4000 rows → ajouter `.limit(2000)` dans B1.

**Features** : `hour` (cyclique sin/cos), `weekday` (cyclique), `platform` (OHE), `weight`
**K** : 6 clusters
**Goal** : profils comportementaux → "Nuit créative", "Étude", "Weekend détente"...

---

### ⏳ PARTIE C — Fusion (à faire après B)

**Notebook** : `03_fusion_visualization.ipynb`

La fusion C1 utilise `km_content_model` depuis Part A — à adapter si on décide de ne plus
utiliser le content clustering. Option : fusion simplifiée = juste les profils behavioral.

---

### ⏳ Home page — Enrichissement CATEGORY_KEYWORDS (à faire)

**Fichier** : `app/pages/home.py`

Modifier `load_all_keywords()` pour scorer les catégories sur les vraies données Delta
au lieu de juste Instagram Topics + X Personalization.

Sources à interroger : `google_searches.query`, `youtube_watch.title`,
`google_chrome.title`, `spotify_streams.artistName`, `netflix_views.show_title`

---

## Fichiers créés

| Fichier | Statut |
|---|---|
| `01_content_clustering.ipynb` | ✅ Run complet, labels A5 définis |
| `02_behavioral_clustering.ipynb` | ⏳ Prêt à lancer (vérifier TikTok/IG volumes d'abord) |
| `03_fusion_visualization.ipynb` | ⏳ À adapter après Part B |
| `warehouse/content_clusters` | ✅ Ecrit (A6) |
| `warehouse/behavioral_clusters` | ⏳ Pas encore |
| `warehouse/interest_profiles` | ⏳ Pas encore |

---

## Prochaines étapes (dans l'ordre)

1. Ouvrir `02_behavioral_clustering.ipynb`
2. Vérifier volumes TikTok + Instagram (cellule dédiée)
3. Lancer B1 → B2 → B3 → B4
4. Lire l'output B4 et définir les labels dans B5
5. Lancer B5 → B6
6. Mettre à jour `app/pages/home.py` pour enrichir les scores CATEGORY_KEYWORDS
