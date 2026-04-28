# MyDigitalTwin — Roadmap Phase 2 : Features & Industrialisation

> **Contexte** : Le PoC (Phase 1) est terminé. Le projet fonctionne localement. La Phase 2 se déroule en deux temps : d'abord développer la nouvelle fonctionnalité "Memory Album", puis industrialiser l'ensemble du projet pour le rendre robuste, reproductible et maintenable.

---

## Vue d'ensemble

```
Phase 2
├── 2A - 2E : Fondations et Nettoyage         ✅ FAIT
├── 2F  Memory Album (Photos × Musique)       🔄 EN COURS
└── 2G  Industrialisation & Qualité           🔄 EN COURS
```

---

## 2F — Memory Album (Photos × Musique) ✨ 🔄 EN COURS

### Vision
Un album photo interactif où des groupes de photos partageant une même ambiance visuelle sont associés à une musique qui correspond à un "moment de vie" similaire.

### Approche Technique (Version "Moments")

**1. Analyse Visuelle : Création des "Moments Visuels"**
- **Input** : Les 30 photos les plus récentes du dossier `data/photos/`.
- **Processing** :
    1. Chaque photo est encodée par le modèle **CLIP** pour obtenir un vecteur sémantique visuel.
    2. Un algorithme de clustering (ex: `HDBSCAN`) est appliqué sur ces 30 vecteurs pour regrouper les photos en **"clusters de moments visuels"** (ex: "paysages de nature", "soirées entre amis").

**2. Analyse Musicale : Création de la "Bibliothèque des Moments Musicaux"**
- **Tâche Manuelle (une seule fois)** :
    1. L'utilisateur sélectionne un large échantillon de ses musiques.
    2. L'utilisateur utilise un **prompt pré-écrit** avec un LLM (ex: dans le chat de l'IDE) pour décrire les "moments de vie" associés à chaque musique.
        > **Prompt** : "Tu es un DJ. Pour chaque musique, décris en 3-5 mots-clés les moments de vie auxquels elle correspondrait. Ex: `Daft Punk - Around the World; Soirée dansante, Nuit en ville, Boost d'énergie`."
    3. L'utilisateur **copie-colle** la sortie du LLM dans un fichier `data/music_moments_library.csv`.
- **Processing Automatique** :
    1. Le script lit ce CSV.
    2. Il encode la description textuelle de chaque "moment musical" avec un modèle comme `all-MiniLM-L6-v2` pour créer une bibliothèque de vecteurs sémantiques.

**3. Matching : Association Moment Visuel ↔ Moment Musical**
- Pour chaque **cluster de photos**, on calcule son vecteur moyen (centroïde).
- On compare ce vecteur de "moment visuel" avec tous les vecteurs de "moments musicaux" via une **similarité cosinus**.
- La musique dont le "moment" est sémantiquement le plus proche est associée à l'ensemble du cluster de photos.

**4. Interface Utilisateur**
- Une nouvelle page `/memory-album` organisée par "scènes" (les clusters de photos).
- Chaque scène affiche la musique associée et la galerie des photos correspondantes.

### Actions
- [ ] Créer un notebook `src/scripts/03_memory_album.ipynb` pour implémenter ce pipeline.
- [ ] Développer la page Dash "Memory Album".

---

## 2G — Industrialisation & Qualité 🔄 EN COURS

### Objectif
Transformer le projet d'un PoC local en un produit de données robuste, reproductible et maintenable, prêt à accepter des contributions externes.

**1. Ingestion Incrémentale (Niveau 2)**
- **Objectif** : Ne traiter que les nouvelles données au lieu de tout recalculer à chaque exécution.
- **Action** : Remplacer `df.write.mode("overwrite")` par des opérations `MERGE INTO` de Delta Lake. Cela nécessite de définir une clé primaire unique pour chaque table.
- **Tâches** :
    - [x] Documenter les clés primaires de chaque table dans `docs/ingestion_keys.md`.
    - [ ] Refactoriser les notebooks du `warehouse` pour utiliser `MERGE INTO`.

**2. Reproductibilité & Configuration**
- **Objectif** : Permettre à un nouvel utilisateur de cloner le projet, remplir un fichier de configuration unique, et lancer tous les services sans erreur.
- **Action** : Éliminer tout code "hardcodé" en centralisant les chemins et constantes projet dans `config.py`, les données personnelles non secrètes dans `config.yaml`, et les secrets dans `.env`.
- **Tâches** :
    - [x] Auditer `src/scripts/`, `src/ingestion/` et `app/` pour repérer les chemins, constantes, ports et paramètres encore hardcodés.
    - [x] Déplacer les chemins et constantes partagés dans `config.py`.
    - [x] Déplacer les paramètres personnels non secrets dans `config.yaml`.
    - [x] Vérifier que le fichier `.env.example` est complet, que les secrets sont correctement chargés et que les erreurs de configuration sont explicites.
    - [ ] Valider le parcours "nouvel utilisateur" : cloner, renseigner `config.yaml` et `.env`, puis lancer ingestion, notebooks et app sans modification du code.

**3. Tests & Qualité des données**
- **Objectif** : Mettre en place un filet de sécurité automatisé pour détecter les régressions et les problèmes de données.
- **Action** : Intégrer `pytest` pour lancer à la fois des tests unitaires, des tests de qualité de données et des tests d'invariants utiles aux notebooks.
- **Tâches** :
    - [x] Configurer `pytest` dans le projet (`pytest.ini`, `tests/conftest.py`).
    - [x] Écrire des **tests unitaires** pour les fonctions critiques (ex: les parsers d'ingestion Google et Spotify).
    - [x] Écrire des **tests de qualité de données** qui valident les tables du `warehouse` et les jeux de données intermédiaires consommés par les notebooks.
    - [x] Vérifier les invariants les plus utiles : `nulls` sur colonnes critiques, types attendus, plages de dates cohérentes, unicité de clés logiques, volumes minimaux et cohérence simple entre tables.

**4. CI/CD & Automatisation (Gestion des PRs)**
- **Objectif** : Automatiser les vérifications de qualité et agir comme un garde-fou pour les contributions.
- **Action** : Créer un workflow GitHub Actions qui s'exécute sur chaque `push` et chaque **Pull Request (PR)**.
- **Tâches** :
    - [x] Créer le fichier `.github/workflows/ci.yml`.
    - [x] Configurer le workflow pour qu'il agisse comme un **"status check" obligatoire** pour les PRs.
    - [x] Le workflow doit lancer :
        1.  **Linting (`ruff`)** : Vérification du style de code.
        2.  **Tests (`pytest`)** : Vérification de non-régression et de qualité des données.
    - [ ] **(Optionnel)** Configurer une règle de branche sur GitHub pour interdire la fusion d'une PR si le workflow échoue.

**5. Évaluation d'outils avancés**
- **Objectif** : Évaluer la pertinence d'outils MLOps standards pour la prochaine phase du projet.
- **Action** : Rédiger une courte analyse sur l'intérêt d'intégrer des outils plus avancés.
- **Tâches** :
    - [ ] **DVC (Data Version Control)** : Analyser le besoin de versionner les données pour une reproductibilité historique parfaite.
    - [ ] **Kedro** : Évaluer si la complexité des notebooks justifie une migration vers un framework de pipeline de données plus structuré.

---

## Priorités

| Priorité | Tâche | Statut |
|---|---|---|
| 🔴 NEXT | **Memory Album : Notebook `03_memory_album.ipynb` (CLIP matching)** | À faire |
| 🔴 NEXT | **Memory Album : Page Dash** | À faire |
| 🟠 P2 | **Industrialisation** : Finir les tâches de la section 2G (Validation nouveau user, MERGE INTO, etc.) | Après le Memory Album |
| 🧊 PAUSE | **Infrastructure Cloud (R2)** | En attente |

---

*Roadmap rédigée le 2026-04-24 — mise à jour le 2026-04-28 (Focus sur Memory Album, puis Industrialisation avec configuration reproductible, tests orientés données et gestion des PRs).*