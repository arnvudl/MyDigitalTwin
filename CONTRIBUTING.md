# Guide de Contribution : MyDigitalTwin

Bienvenue ! Ce document définit les standards et les bonnes pratiques pour contribuer à la base de code de MyDigitalTwin. L'objectif de ces règles est de garantir que le projet reste **robuste, reproductible et facile à maintenir** sur le long terme.

---

## 1. La Règle d'Or : La Configuration Centralisée

Le principe fondamental de ce projet est l'**absence totale de valeurs "hardcodées"** dans les scripts et les notebooks. N'importe quel utilisateur doit pouvoir cloner le projet et le faire tourner sur ses propres données en modifiant uniquement les fichiers de configuration.

*   **Chemins et Dossiers :** Ne jamais écrire de chemins de fichiers en dur (ex: `pd.read_parquet("C:/Users/.../data/warehouse/...")`). Utilisez toujours les variables définies dans `config.py` (ex: `os.path.join(WAREHOUSE, "nom_de_la_table")`).
*   **Paramètres Spécifiques :** Les noms de comptes (ex: votre pseudo Instagram), les artistes favoris, ou les seuils d'algorithmes doivent être définis dans `config.py`.
*   **Secrets et Clés d'API :** Ne **JAMAIS** écrire de mot de passe, de token ou de clé d'API dans le code source ou dans `config.py`.
    *   Ces valeurs doivent être placées dans un fichier `.env` à la racine du projet (ce fichier est ignoré par Git).
    *   Le fichier `config.py` se charge de lire ces variables d'environnement.
    *   Si vous ajoutez une nouvelle variable secrète, ajoutez-la également au fichier `.env.example` avec une valeur factice pour documenter son existence.

## 2. Architecture de Configuration (3 fichiers, 3 rôles)

La configuration est séparée en trois fichiers avec des responsabilités strictes :

| Fichier | Contient | Commité dans Git ? |
|---|---|---|
| `config.py` | Chemins, détection d'environnement, `build_spark_session()` | ✅ Oui |
| `config.yaml` | Données personnelles (pseudo Instagram, close friends, artistes…) | ✅ Oui (données non-sensibles) |
| `.env` | Clés d'API, tokens, secrets | ❌ Non (`.gitignore`) |

### `config.py` — Ne jamais modifier directement pour des données perso

Ce fichier gère automatiquement les trois environnements d'exécution :

```
Local            → data/ dans le projet
Docker Spark     → /opt/spark/data/
Docker Dashboard → /app/data/
```

Il expose aussi `build_spark_session()` pour les notebooks :

```python
from config import build_spark_session, WAREHOUSE

# Appel standard (4 Go, 8 partitions, Delta activé)
spark = build_spark_session("MonApp")

# Avec override si le dataset est plus lourd
spark = build_spark_session("MonApp", driver_memory="6g")

# Sans Delta Lake ni compression Snappy
spark = build_spark_session("MonApp", delta=False, snappy=True)
```

Paramètres disponibles :

| Paramètre | Défaut | Description |
|---|---|---|
| `driver_memory` | `"4g"` | RAM allouée au driver Spark |
| `shuffle_partitions` | `8` | Partitions après un shuffle (réduire pour petits datasets) |
| `delta` | `True` | Active les extensions Delta Lake |
| `snappy` | `False` | Active la compression Snappy pour Parquet |
| `master` | `"local[*]"` | URL du cluster (`local[*]` = tous les cœurs locaux) |

### `config.yaml` — Le seul fichier à personnaliser

C'est **l'unique fichier à modifier** pour adapter le projet à vos propres données. Un `config.yaml.example` est fourni comme point de départ.

### Docker : monter les deux fichiers

Les containers Spark et Dashboard ont besoin de `config.py` et `config.yaml`. Le `docker-compose.yml` les monte automatiquement — ne pas les retirer des volumes.

---

## 3. Le Flux de Données (Architecture Medallion Simplifiée)

Le projet suit un flux de données strict pour garantir l'intégrité des analyses :

1.  **`data/inbox/` (Bronze) :** Zone de dépôt temporaire pour les archives brutes (fichiers ZIP GDPR). Ne jamais lire ces données directement pour une analyse.
2.  **`data/processed/` (Silver) :** Données extraites, nettoyées et standardisées par les scripts d'`ingestion/`. C'est la source de vérité pérenne.
3.  **`data/warehouse/` (Gold) :** Tables analytiques enrichies (format Parquet/Delta) générées par les notebooks, prêtes à être consommées par le Dashboard.

**Règle pour les Notebooks :** Les notebooks d'exploration et de feature engineering ne doivent lire les données **que** depuis `processed/` (pour créer de nouvelles tables) ou depuis `warehouse/` (pour croiser des données existantes).

## 4. Qualité du Code et Tests

*   **Linting et Formatage :** Nous utilisons `ruff` pour garantir un style de code Python cohérent et identifier les erreurs courantes. Assurez-vous que votre code passe les vérifications de `ruff` avant de soumettre des modifications.
*   **Notebooks Propres :** Avant de commiter un notebook Jupyter, assurez-vous qu'il s'exécute de bout en bout sans erreur ("Restart & Run All"). Supprimez les cellules de test inutiles et nettoyez les sorties (outputs) si elles contiennent des données personnelles volumineuses ou sensibles.
*   **Tests (`pytest`) :** Le projet intègre une suite de tests automatisés.
    *   **Tests Unitaires (`tests/unit/`) :** Toute nouvelle fonction logique (parsers, helpers) doit être accompagnée de son test unitaire. Les tests unitaires doivent être rapides et ne pas dépendre du dataset complet (utiliser des fixtures). Exécutez-les avec `pytest -m unit`.
    *   **Tests de Qualité de Données (`tests/data_quality/`) :** Ces tests valident le contenu final du `warehouse` (pas de valeurs nulles inattendues, volumes cohérents, pas de dates dans le futur). Exécutez-les avec `pytest -m data_quality`.

## 5. Processus de Contribution (Pour les collaborateurs)

Si vous souhaitez contribuer au projet :

1.  **Bifurquez (Fork) le dépôt** et créez une branche pour votre fonctionnalité ou correction de bug (ex: `feature/nouvel-export-spotify` ou `fix/parser-instagram`).
2.  **Développez et testez** localement en vous assurant de respecter les règles de configuration (voir point 1). Assurez-vous que tous les tests passent (`pytest`).
3.  **Vérifiez le code** avec le linter (`ruff`).
4.  **Soumettez une Pull Request (PR)** décrivant clairement les changements apportés.
5.  **Intégration Continue (CI)** : Votre PR déclenchera automatiquement des vérifications (linting, tests unitaires) via GitHub Actions. Les PRs ne pourront être fusionnées que si tous ces voyants sont au vert.

---

*Merci de votre aide pour faire de MyDigitalTwin un projet d'ingénierie de données exemplaire !*