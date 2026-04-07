# Rapport : Optimisation du Système de Recommandation (ALS & Sémantique)
_Date : 6 Avril 2026_

## 1. Problématique Initiale
Le système de recommandation basé sur l'algorithme **ALS (Alternating Least Squares)** présentait des scores incohérents avec les goûts réels de l'utilisateur :
*   **Biais de Plateforme :** Les données Spotify (33k streams) écrasaient les données Netflix (4k views). Un morceau de musique comptait autant qu'un film de 2h.
*   **Biais de Fréquence :** L'algorithme privilégiait l'intensité de consommation (binge-watching) plutôt que l'appréciation réelle. Une série regardée "en fond" obtenait un score de 100%, tandis qu'un coup de cœur comme *Naruto* tombait à 6%.
*   **Absence de Sémantique :** L'IA ne comprenait pas les genres (Anime vs Horreur). Elle traitait les titres comme de simples IDs sans lien logique.

## 2. Solutions Implémentées

### A. Normalisation et Rééquilibrage
*   **Poids Plateforme :** Dans `01_build_interactions.ipynb`, nous avons appliqué un facteur d'échelle pour que le poids total de Netflix soit égal à celui de Spotify.
*   **Log-Scaling :** Application de la fonction `log1p` sur les interactions pour réduire l'impact des visions répétées et lisser la différence entre une série longue et un film unique.

### B. Enrichissement Sémantique (Ollama)
*   **Script `01b_semantic_enrichment.py` :** Utilisation d'un LLM local (**Mistral-Nemo 12B / Gemma2 9B**) via Ollama pour classifier chaque titre.
*   **Sortie :** `Catégorie | Genre | Sous-Genre | Ambiance`.
*   **Performance :** Traitement de ~4000 items en ~2h20 avec parallélisme léger (4 threads) pour optimiser l'usage du GPU (8Go VRAM).

### C. Profilage "Expert" (Hybride)
*   **Fichier `top.md` :** Intégration d'un fichier de préférences explicites pour ancrer le profil Netflix sur des titres adorés (Tenet, Naruto, etc.).
*   **Ancrage Artiste :** Le profil Spotify est désormais ancré sur une liste d'artistes favoris (Damso, Tiakola, etc.) plutôt que sur les titres les plus écoutés.
*   **Boost Sémantique :** Application d'un bonus de **+50%** sur le score final pour les items correspondant aux genres favoris détectés dans le profil de l'utilisateur.

## 3. Défis Techniques Résolus
*   **PySpark Types :** Correction de nombreuses erreurs `Py4JJavaError` et `PySparkTypeError` causées par des conflits de types entre les `floats` de Pandas (ex: 9.0) et les `integers` de Spark (ex: 9). Résolu par un casting explicite et une conversion robuste en dictionnaires.
*   **Dash ReferenceError :** Correction d'un bug d'animation sur la page `/recommandations` où l'ID du compteur de score n'était pas trouvé par le callback clientside.
*   **Fuzzy Matching :** Utilisation de `difflib` et de regex pour faire correspondre les titres du fichier `top.md` avec l'historique de consommation, malgré les emojis ou les différences de formatage.

## 4. Architecture Actuelle
Le pipeline se déroule désormais comme suit :
1.  **Notebook 01 :** Unification + Normalisation des poids (Spotify vs Netflix).
2.  **Script 01b :** Classification sémantique via IA locale (Ollama).
3.  **Notebook 02 :** Entraînement de deux modèles ALS isolés (un par plateforme) + Calcul du score hybride (ALS + Boost sémantique).
4.  **Dashboard :** Page `/recommandations` affichant le score final et les métadonnées de l'IA.

## 5. Prochaines Étapes
*   **Affinement du Boost :** Ajuster le `BOOST_FACTOR` si certaines séries "bruit" remontent encore trop haut.
*   **Cold Start :** Utiliser les genres du LLM pour recommander des films jamais vus (recommandation basée uniquement sur le contenu).
