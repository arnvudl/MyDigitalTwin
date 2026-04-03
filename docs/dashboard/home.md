## 📋 Spec — Page Home

### Sources de données
| Fichier | Ce qu'on extrait |
|---|---|
| `google_searches.parquet` | Mots-clés de recherche |
| `youtube_watch.parquet` | Titres de vidéos |
| `tiktok_watch.parquet` | Titres/tags de vidéos |
| `spotify_streams.parquet` | Artistes, genres |
| `instagram_likes.parquet` | Tags/topics |
| `twitter_likes.parquet` | Mots-clés tweets likés |
| `amazon_orders.parquet` | Catégories produits |
| `raw/INSTAGRAM/ads_and_topics/posts_not_interested.json` | Centres d'intérêt détectés Instagram |
| `raw/INSTAGRAM/ads_and_topics/ads_clicked.json` | Intérêts publicitaires cliqués |
| `raw/X/data/ad-impressions.js` | Intérêts publicitaires X |
| `raw/X/data/ad-engagements.js` | Engagements pub X |

### Ce qu'on affiche
- **Avatar** au centre (ton image)
- **Cercles concentriques** avec les tags qui rayonnent
- **Anneau 1 (proche)** — top 6 catégories : `Musique`, `Tech`, `Sport`...
- **Anneau 2 (milieu)** — exemples concrets par catégorie
- **Anneau 3 (loin)** — tags secondaires, plus petits
- **Clic sur un tag** → zoom + affiche les sources qui ont généré ce tag

### Logique de regroupement
```
Toutes sources → extraction mots-clés → TF-IDF/fréquence 
→ clustering en ~8 catégories → affichage par anneau
```