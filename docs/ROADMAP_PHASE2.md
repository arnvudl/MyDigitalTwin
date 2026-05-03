# MyDigitalTwin — Roadmap Phase 2 : Features & Industrialisation

> **Contexte** : Le PoC (Phase 1) est terminé. Le projet fonctionne localement. La Phase 2 se déroule en deux temps : d'abord développer la nouvelle fonctionnalité "Memory Album", puis industrialiser l'ensemble du projet pour le rendre robuste, reproductible et maintenable.

---

## Vue d'ensemble

```
Phase 2
├── 2A - 2E : Fondations et Nettoyage         ✅ FAIT
├── 2F  Memory Album (Photos × Musique)       ✅ FAIT
├── 2G  Industrialisation & Qualité           🔄 EN COURS
└── 2H  Refonte UI (Réflexion)                ⏳ EN ATTENTE
```

---

## 2F — Memory Album (Photos × Musique) ✨

### Vision
Créer un **album de “moments de vie” multimodaux** où :
- les photos sont regroupées en **scènes cohérentes (visuelles + contextuelles)**
- chaque scène est associée à une **musique crédible et contextualisée**
L'objectif est de reconstruire des **souvenirs**, pas juste grouper des images.

### Approche Technique (Version "Moments Multimodaux")

**1. Analyse des Photos : Création des "Moments Visuels Enrichis"**
- **Input** : Jusqu’à 100 photos récentes (avec métadonnées: date, heure, GPS optionnel).
- **Pipeline de compréhension visuelle (fallback intelligent)** :
    1. **BLIP-2** (prioritaire) : génère une caption riche (ex: *"crowd dancing at night concert with lights"*).
    2. **OpenCLIP** : embedding image + texte.
    3. **CLIP** : fallback léger et rapide.
- **Enrichissement contextuel** :
    - **Temps** : heure (jour/nuit), jour de la semaine/week-end, saison.
    - **GPS** : clustering géographique, détection (domicile, extérieur, voyage).
    - **Continuité temporelle** : boost de similarité pour les photos proches dans le temps.
- **Fusion des embeddings** :
    - Formule de base : `final_embedding = 0.6 * visual_embedding + 0.25 * time_embedding + 0.15 * geo_embedding`
    - **Gestion des données manquantes** : Si `time_embedding` ou `geo_embedding` sont absents, les poids sont dynamiquement ajustés et normalisés pour que leur somme reste à 1.0.
        - `sum_available_weights = (0.6 si visual_embedding existe) + (0.25 si time_embedding existe) + (0.15 si geo_embedding existe)`
        - `final_embedding = (0.6 / sum_available_weights) * visual_embedding` (si disponible)
            `+ (0.25 / sum_available_weights) * time_embedding` (si disponible)
            `+ (0.15 / sum_available_weights) * geo_embedding` (si disponible)
- **Clustering des "moments"** :
    - Utilisation de **HDBSCAN** (gère le bruit, s'adapte à la densité, nombre de clusters inconnu).

**2. Analyse Musicale : Bibliothèque des Moments Musicaux**
- **Source des musiques (3 niveaux)** :
    1. **Historique réel (priorité max)** : musique écoutée au moment exact (match timestamp ↔ photo).
    2. **Bibliothèque personnalisée (JSON)** :
       - **Phase 1 (Manuelle + LLM)** : L'utilisateur sélectionne des musiques. Un LLM génère un fichier JSON avec `titre - artiste - moments` (ex: `{"title": "Around the World", "artist": "Daft Punk", "moments": ["soirée", "énergie", "amis"]}`).
       - **Phase 2 (Script)** : Un script prend ce JSON, identifie les `track_id` et `track_name` correspondants (via une API musicale ou une base de données locale) et enrichit le JSON pour obtenir la structure finale :
         ```json
         {
           "track_id": "...",
           "track_name": "...",
           "moments": ["soirée", "énergie", "amis"]
         }
         ```
    3. **Fallback global (cold start)** : playlist par défaut ou génération via tags du cluster.
- **Embedding des musiques** :
    - Calcul dynamique avec un modèle texte (ex: `embedding = encoder("soirée énergie amis")`). *Pas d'embeddings stockés.*

**3. Matching : Moment Visuel ↔ Moment Musical**
- Calcul du centroïde du cluster photo.
- Comparaison avec les embeddings musicaux (similarité cosinus).
- **Priorité du matching** : 1. Historique réel, 2. Similarité sémantique, 3. Fallback.

**4. Interface Utilisateur**
- Une nouvelle page `/memory-album` organisée par "scènes" (clusters).
- Chaque scène contient : musique associée, galerie de photos, description du moment (optionnel).
- *Bonus UX* : Nom auto généré ("Nuit à Bruxelles"), animation / transition musicale.

### Actions
- [x] Notebooks `src/scripts/03_memory_album/` : 01 embeddings BLIP-2/OpenCLIP, 02 clustering temporel, 03 matching musical.
- [x] Implémenter le script de la Phase 2 pour la bibliothèque musicale JSON (via Spotify API).
- [x] Développer la page Dash "Memory Album" (`/memory-album`) — layout vertical, music par scène.
- [x] Corriger les bugs post-lancement : doublons Delta, encodage URLs, clustering inter-dates, perf.

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

**2. Reproductibilité & Configuration (Migration vers Copier)**
- **Objectif** : Permettre à un nouvel utilisateur de cloner le projet, remplir un fichier de configuration unique, et lancer tous les services sans erreur. Mais aussi de pouvoir **mettre à jour** la structure de son projet facilement par la suite.
- **Action** : Transformer le projet en un template standardisé avec **Copier** (plutôt que Cookiecutter) pour gérer les mises à jour futures via `copier update`. Continuer d'éliminer tout code "hardcodé".
- **Tâches** :
    - [x] Auditer `src/scripts/`, `src/ingestion/` et `app/` pour repérer les chemins, constantes, ports et paramètres encore hardcodés.
    - [x] Déplacer les chemins et constantes partagés dans `config.py`.
    - [x] Déplacer les paramètres personnels non secrets dans `config.yaml`.
    - [x] Vérifier que le fichier `.env.example` est complet, que les secrets sont correctement chargés et que les erreurs de configuration explicites.
    - [ ] **NOUVEAU** : Mettre en place la structure du template **Copier** (`copier.yml`, `{{ cookiecutter.project_name }}` -> syntaxe Copier).
    - [ ] Valider le parcours "nouvel utilisateur" : générer le projet avec Copier, renseigner les configs, puis lancer ingestion, notebooks et app sans modification du code.

**3. Tests & Qualité des données**
- **Objectif** : Mettre en place un filet de sécurité automatisé pour détecter les régressions et les problèmes de données.
- **Action** : Intégrer `pytest` pour lancer à la fois des tests unitaires, des tests de qualité de données et des tests d'invariants utiles aux notebooks. **Intégrer Pandera pour des contrats de données robustes sur les DataFrames Spark.**
- **Tâches** :
    - [x] Configurer `pytest` dans le projet (`pytest.ini`, `tests/conftest.py`).
    - [x] Écrire des **tests unitaires** pour les fonctions critiques (ex: les parsers d'ingestion Google et Spotify).
    - [ ] **NOUVEAU** : Intégrer **Pandera** pour définir des schémas de validation stricts sur les DataFrames PySpark (ex: pas de nulls sur `track_id`, limites sur `latitude`).
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

**6. Documentation**
- **Objectif**: Documenter l'architecture de production et les décisions techniques.
- **Tâches**:
    - [ ] [PROD1.md](./PROD1.md) - Architecture de Production Cible.
    - [ ] [PROD2.md](./PROD2.md) - Analyse des Coûts et Services.

---

## 2H — Refonte UI (Réflexion) ⏳ EN ATTENTE

### Objectif
Réfléchir à une modernisation complète de l'interface utilisateur de l'application Dash en utilisant des composants plus riches et esthétiques.

**Action envisagée :**
- Étudier l'intégration de la librairie **Dash Mantine Components (DMC)**.
- Cela permettrait de remplacer les composants Dash natifs (souvent basiques visuellement) par des composants basés sur React Mantine, offrant des designs modernes, le support du Dark Mode natif, et une meilleure ergonomie (cartes, notifications, etc.).

---

## Priorités

| Priorité | Tâche | Statut |
|---|---|---|
| ✅ FAIT | **Memory Album** : notebooks, matching musical, page Dash, corrections bugs | Terminé |
| 🔴 NEXT | **Industrialisation** : Copier template, MERGE INTO, Tests Pandera | En cours (2G) |
| 🟠 P2 | **Validation nouveau user** : générer le projet avec Copier, lancer ingestion + app | Après Copier |
| 🧊 PAUSE | **Infrastructure Cloud (R2)** | En attente |

---

*Roadmap rédigée le 2026-04-24 — mise à jour le 2026-05-02 (2F Memory Album terminé ; focus 2G Industrialisation).*