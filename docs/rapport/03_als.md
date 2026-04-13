# Phase 03 — Système de Recommandation ALS

_Dossier_ : `src/scripts/03_als/`  
_Statut_ : 🔜 En cours  
_Notebooks_ : `01_build_interactions`, `02_als_model`  
_Scripts_ : `01b_semantic_enrichment.py`  
_Outputs_ : `data/warehouse/interactions`, `data/warehouse/als_scores`, `data/warehouse/item_metadata.parquet`

---

## Objectif

Produire un score de recommandation personnalisé "Arnaud aimera à X%" pour les contenus Spotify et Netflix, exploitable dans le dashboard (`/recommandations`, `/netflix`, `/spotify`).

---

## Évolution de l'approche

### Ce qui a été abandonné : ALS sur données personnelles uniquement

Une première version utilisait uniquement les données perso (Spotify + Netflix) pour entraîner l'ALS. Le problème : **~400 items distincts** après filtre — trop peu pour que la factorisation de matrice converge vers quelque chose de significatif. ALS a besoin de co-occurrences riches (item X vu par plusieurs utilisateurs), impossible avec un seul utilisateur réel.

### Approche retenue : ALS sur MovieLens 32M + données personnelles

On fusionne les **32 millions de notes MovieLens** (base collaborative mondiale) avec les vues personnelles Netflix pour entraîner un ALS global. Le profil d'Arnaud est ensuite projeté dans cet espace latent via des ancres manuelles.

**Pourquoi MovieLens fait la différence** :
- Chaque film a des centaines/milliers de notes → les vecteurs latents sont bien définis.
- Le profil d'Arnaud (ses films Netflix) bénéficie de ces représentations riches.
- Les recommandations sont basées sur "qui d'autre aime les mêmes films" — le vrai signal collaboratif.

**Voir** : `docs/nouvelle_als.md` pour le détail de l'architecture MovieLens 32M.

---

## Choix de l'algorithme : ALS Implicite

### Pourquoi ALS ?

ALS (Alternating Least Squares) est l'algorithme de référence pour la factorisation de matrices dans les systèmes de recommandation collaboratifs. Il est natif dans **Spark MLlib**, ce qui permet de l'entraîner directement sur les DataFrames Spark sans sortir du pipeline.

### Pourquoi "implicite" (pas explicite) ?

- Les données perso sont des **comportements** (écoutes Spotify, visionnages Netflix), pas des **notes** explicites.
- `implicitPrefs=True` dans Spark ALS traite le `play_count` comme un indicateur de préférence pondéré : plus on écoute, plus la confiance est haute.
- MovieLens contient des notes explicites (0.5-5.0), converties en signal implicite pondéré lors de la fusion.

### Pourquoi pas du Deep Learning (NCF, BERT4Rec) ?

- Ces modèles surpassent ALS à partir de plusieurs millions d'interactions **personnelles**.
- Avec un seul utilisateur réel, on n'a pas ce volume même avec MovieLens comme pont.
- ALS est interprétable : les vecteurs d'items peuvent être comparés directement via cosine similarity.
- Spark MLlib = aucune dépendance supplémentaire (pas de PyTorch/TensorFlow).

---

## Construction des Interactions (01_build_interactions)

### Sources retenues : Spotify + Netflix uniquement

YouTube a été exclu malgré ses 13 000 lignes. Raison : trop de bruit (pubs, vidéos auto-play, streams en background). Le signal "j'ai regardé une vidéo" est beaucoup moins fiable que "j'ai écouté une chanson pendant 3 minutes".

### Virtual Users = Mois

Arnaud est un seul utilisateur réel. L'encodage `user_id = year * 100 + month` transforme chaque mois d'activité en "profil" distinct. Cela donne une dimension utilisateur à ALS pour détecter des évolutions temporelles dans les goûts.

### Normalisation des plateformes

Sans normalisation, Spotify (33k streams) écraserait Netflix (4k views). Un facteur d'échelle par plateforme (`max_count / platform_count`) rééquilibre les contributions.

### Filtre : items vus dans >= 2 mois distincts

Items vus un seul mois = signal potentiellement aléatoire. >= 2 mois = préférence réelle.

**Optimisation** : `interactions_agg` est mis en `.cache()` car utilisé 2 fois (stats + jointure filtre bruit).

---

## Modèle ALS (02_als_model)

### Hyperparamètres

| Paramètre | Valeur | Justification |
|---|---|---|
| `rank` | 20 | Dimension des vecteurs latents. |
| `maxIter` | 20 | Convergence suffisante sur ce volume. |
| `regParam` | 0.15 | Régularisation L2 anti-overfitting. |
| `implicitPrefs` | True | Données comportementales. |

### Log scaling

`weight = log1p(play_count)` : compresse les valeurs extrêmes sans perdre l'ordonnancement.

### Profil via ancres

Arnaud n'a qu'un seul user_id réel → on ne peut pas simplement appeler `model.recommendForUser()`. Solution : définir des **ancres** (titres favoris connus manuellement) pour construire un vecteur profil moyen, puis calculer la cosine similarity avec tous les items.

---

## Enrichissement Sémantique (01b_semantic_enrichment.py)

Enrichit `item_metadata.parquet` avec des embeddings sémantiques (sentence-transformers) pour permettre une recommandation hybride (collaborative + contenu). Utilisé aussi par la phase 04 (clone RAG).

---

## Ce qui reste à faire

- [ ] Intégrer MovieLens 32M dans le pipeline (ingest + fusion avec données perso)
- [ ] Connecter les scores ALS aux pages `/netflix` et `/spotify` du dashboard
- [ ] Tester le carousel "Recommandé pour toi"
