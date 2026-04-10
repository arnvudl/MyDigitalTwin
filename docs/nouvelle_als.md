# Évolution du Système de Recommandation (Digital Twin)
_Document de Synthèse Technique — Avril 2026_

---

_paulinalambin

adamvdd

alicedbgf

clara_dtr_

erwan_dnln

fada_bob.1

flavie.kdl

gabriel_bucur_10

hugo_bernard._

jen.shr

jex.brg._

laura.barreto_

leny.soetaerts

llaure_mrt

louisechenoy

louna_vlt_

lucie_lks

luka_olivier_

luna.tstt

manon_vandy

mstph.smb

mylene_arj

romane_dsrt

sachou_wz

thibmadabel

tom_bern_

victoriastofleth

vyktor.g

zoeline.rms

---

## 1. L'Approche Initiale (Le "Avant") 📉

La V1 reposait sur une structure ingénieuse mais limitée par le manque de précision des données sources.

* **Classification Universelle (Ollama) :** Utilisation d'un LLM local pour classifier Netflix et Spotify à partir des noms uniquement.
    * *Problème :* Hallucinations sur les genres musicaux (ex: musiques africaines classées en "Electronic") par manque de contexte acoustique.
* **Logique ALS Temporelle :** Utilisation de "Virtual Users" par mois pour simuler une matrice de recommandation.
    * *Problème :* L'IA recommande ce qui est consommé "en même temps" plutôt que ce qui se ressemble sémantiquement.
* **Ancrage Statique :** Application d'un bonus fixe de +50% basé sur un simple "Fuzzy Matching" (correspondance de texte) avec le fichier `top.md`.
    * *Problème :* Si un titre est mal orthographié ou absent du top, il ne bénéficie d'aucun boost, même s'il correspond au genre favori.

---

## 2. La Nouvelle Stratégie (Le "Après") 🚀

L'objectif est d'injecter de la "Vérité Terrain" et de la mathématique vectorielle pour un ranking chirurgical.

### A. Enrichissement via LLM Généraliste (Manuel)
* **Extraction Bulk :** Export de tous les items (`item_title`, `platform`) en CSV depuis `interactions.parquet`.
* **Traitement Manual :** Drag&drop du CSV dans Claude/GPT/Gemini (ou batch par ~1000 items).
* **Sortie Structurée :** LLM retourne `item_title | platform | category | genre | sub_genre | mood` en CSV strict.
* **Import en Parquet :** CSV enrichi → `warehouse/item_metadata.parquet` (Delta Lake).
* **Raison :** Les genres Spotify sont supprimés (API récente). Un LLM généraliste comprend mieux *Naruto = Anime/Action* et *Afro-Pop* que Ollama local ou APIs tierces.

### B. Passage au "Content-Based" Vectoriel
* **Embeddings de Genres :** Word2Vec/FastText sur `genre | sub_genre | mood` pour transformer chaque item en vecteur numérique.
* **Profil Utilisateur :** Centre de gravité sémantique calculé depuis les items favoris de `top.md` (moyenne des vecteurs).
* **Similarité Cosinus :** Distance mathématique entre chaque item et votre profil = `score_semantic`.

### C. Scoring Hybride Dynamique
Le score final de recommandation ne sera plus un simple pourcentage ALS, mais une fusion pondérée :
$$Score_{Final} = \\alpha \\cdot Score_{ALS} + (1 - \\alpha) \\cdot Score_{Sémantique}$$

* **L'ALS** apporte la découverte liée à vos habitudes de consommation.
* **La Sémantique** garantit que l'item correspond à votre ADN culturel.

---

## 3. Gains Attendus 🎯

1.  **Précision Chirurgicale :** Fin des erreurs de genres sur la musique africaine et les niches spécifiques.
2.  **Résolution du Cold Start :** Capacité à recommander un film que vous n'avez *jamais* vu, simplement parce que son vecteur sémantique est proche de vos favoris.
3.  **Ranking Cohérent :** Un système qui comprend qu'un fan de *Naruto* aimera probablement *Jujutsu Kaisen*, même sans historique de visionnage commun.

---

## 4. Pipeline d'Exécution (Notebooks)

```
warehouse/spotify_streams + netflix_views
        ↓
Notebook 01_build_interactions.ipynb (INCHANGÉ)
        ↓
warehouse/interactions.parquet
        ↓
[Export CSV + Enrichissement LLM manuel (Claude/GPT)]
        ↓
warehouse/item_metadata.parquet
        ↓
Notebook 02_als_model.ipynb (À REFAIRE — V2 Hybride)
  - Charger interactions + item_metadata
  - Word2Vec/FastText sur genres
  - Calculer score_ALS (vecteurs latents ALS)
  - Calculer score_semantic (cosinus similarity)
  - Fusionner : score_final = α·ALS + (1-α)·Semantic
        ↓
warehouse/als_scores.parquet
```

**Fichiers modifiés :**
- ❌ `01b_semantic_enrichment.py` : **Supprimé** (remplacé par drag&drop CSV)
- ❌ `02_als_model.ipynb` : **À refaire** pour intégrer embeddings vectoriels + scoring hybride
- ✅ `01_build_interactions.ipynb` : **Inchangé**