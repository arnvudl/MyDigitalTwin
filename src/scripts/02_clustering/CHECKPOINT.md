# Checkpoint — Clustering
_Dernière mise à jour : 2026-04-06_

---

## État actuel

### ✅ PARTIE A — Content Clustering (remplacée par analyse fréquentielle)

**Notebook** : `01_content_clustering.ipynb`

**Résultat** : K-Means k=15 sur TF-IDF produisait un cluster catch-all dominant (~73%, Silhouette 0.19).
**Décision** : remplacé par une **analyse fréquentielle par source** (PySpark Tokenizer + NGram + comptage).

**Ce que le notebook fait maintenant** :
1. Fréquence de mots par source (Google, YouTube, Spotify, Netflix, Chrome)
2. Bigrammes pour les termes composés ("travis scott", etc.)
3. Gap analysis vs CATEGORY_KEYWORDS
4. Tableau des mises à jour appliquées à `home.py`

**Findings appliqués dans `app/pages/home.py`** :
- Musique : ajout `damso`, `tiakola`, `zamdane`, `bezbar`, `travis scott`, `squeezie`
- Cinéma/Séries : ajout `naruto`, `shippuden`, `fairy tail`, `jojo`, `baki`, `boruto`, `one piece`
- Actu : ajout `belgique`
- Retraits : `"league"` (matchait LoL), `"luxury"` (matchait luxury car), `"style"` (matchait "by Body Type & Style")

**Enrichissement Delta** : `load_all_keywords()` dans `home.py` score maintenant sur les vraies données
Delta (google_searches, youtube_watch, google_chrome, spotify_streams, netflix_views).

---

### ✅ PARTIE B — Behavioral Clustering (terminée, labels définis)

**Notebook** : `02_behavioral_clustering.ipynb`

**Features** : `hour_sin/cos`, `weekday_sin/cos`, `weight`, `platform_ohe`
**K** : 6 clusters

**Résultats** :
| Cluster | Label | Items | Plateforme | Moment |
|---|---|---|---|---|
| 0 | 📺 YouTube · Après-midi | 13,821 | youtube | Après-midi semaine |
| 1 | 🛋️ Soirée connectée | 31,774 | google+netflix+instagram | Soir semaine |
| 2 | 📱 TikTok · Scroll | 2,000 | tiktok (limité) | Après-midi semaine |
| 3 | 🎵 Spotify · Journée | 33,972 | spotify | Après-midi semaine |
| 4 | 💻 Navigation · Soir | 338 | chrome | Soir semaine |
| 5 | 🔍 Recherches · Journée | 30,368 | google | Après-midi semaine |

**Note V2 testée** : retrait de la plateforme → doublons (2× "Soir Semaine", 2× "Weekend"), Silhouette 0.33. V1 conservée car la plateforme est un signal comportemental valide.

**Limite TikTok/Instagram** : `.limit(2000)` pour équilibrer le poids des sources (TikTok = 234k rows bruts).

**⏳ À faire** : lancer B6 pour écrire `warehouse/behavioral_clusters`

---

### ✅ PARTIE C — Fusion (terminée)

**Notebook** : `03_fusion_visualization.ipynb`

Fusion simplifiée = profils behavioral uniquement (content clustering abandonné).
Toutes références à `km_content_model` / `content_clusters` retirées.

---

### ✅ Home page — Enrichissement CATEGORY_KEYWORDS

**Fichier** : `app/pages/home.py`

✅ `load_all_keywords()` enrichi avec données Delta
✅ Keywords mis à jour (ajouts + retraits)
✅ Home page utilise exclusivement les données Delta Lake (notebooks → page `/profils`)

---

## Fichiers créés

| Fichier | Statut |
|---|---|
| `01_content_clustering.ipynb` | ✅ Analyse fréquentielle complète |
| `02_behavioral_clustering.ipynb` | ✅ Complet (B1→B6) |
| `03_fusion_visualization.ipynb` | ✅ Complet (C1→C3 + D1) |
| `warehouse/content_clusters` | ✅ Ecrit (ancien run K-Means, non utilisé) |
| `warehouse/behavioral_clusters` | ✅ Ecrit — 6 profils |
| `warehouse/interest_profiles` | ✅ Ecrit — 6 profils + keywords + samples |

---

## Prochaines étapes

✅ Toute la partie clustering est terminée.

→ Passer à l'axe suivant selon `docs/ml_source_plan.md` :
- **Axe 1 — Clone NLP** : `text_corpus.parquet` + TF-IDF + N-grams
- **Axe 2 — Recommandations ALS** : `interactions.parquet` + ALS
