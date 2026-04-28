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

## 2. Le Flux de Données (Architecture Medallion Simplifiée)

Le projet suit un flux de données strict pour garantir l'intégrité des analyses :

1.  **`data/inbox/` (Bronze) :** Zone de dépôt temporaire pour les archives brutes (fichiers ZIP GDPR). Ne jamais lire ces données directement pour une analyse.
2.  **`data/processed/` (Silver) :** Données extraites, nettoyées et standardisées par les scripts d'`ingestion/`. C'est la source de vérité pérenne.
3.  **`data/warehouse/` (Gold) :** Tables analytiques enrichies (format Parquet/Delta) générées par les notebooks, prêtes à être consommées par le Dashboard.

**Règle pour les Notebooks :** Les notebooks d'exploration et de feature engineering ne doivent lire les données **que** depuis `processed/` (pour créer de nouvelles tables) ou depuis `warehouse/` (pour croiser des données existantes).

## 3. Qualité du Code

*   **Linting et Formatage :** Nous utilisons `ruff` pour garantir un style de code Python cohérent et identifier les erreurs courantes. Assurez-vous que votre code passe les vérifications de `ruff` avant de soumettre des modifications.
*   **Notebooks Propres :** Avant de commiter un notebook Jupyter, assurez-vous qu'il s'exécute de bout en bout sans erreur ("Restart & Run All"). Supprimez les cellules de test inutiles et nettoyez les sorties (outputs) si elles contiennent des données personnelles volumineuses ou sensibles.
*   **Tests (À venir) :** Le projet intègre `pytest`. Toute nouvelle fonction critique, en particulier les parsers dans `src/ingestion/`, devrait idéalement être accompagnée d'un test unitaire dans le dossier `tests/`.

## 4. Processus de Contribution (Pour les collaborateurs)

Si vous souhaitez contribuer au projet :

1.  **Bifurquez (Fork) le dépôt** et créez une branche pour votre fonctionnalité ou correction de bug (ex: `feature/nouvel-export-spotify` ou `fix/parser-instagram`).
2.  **Développez et testez** localement en vous assurant de respecter les règles de configuration (voir point 1).
3.  **Vérifiez le code** avec le linter (`ruff`).
4.  **Soumettez une Pull Request (PR)** décrivant clairement les changements apportés.
5.  **Intégration Continue (CI)** : Votre PR déclenchera automatiquement des vérifications (linting, tests unitaires) via GitHub Actions. Les PRs ne pourront être fusionnées que si tous ces voyants sont au vert.

---

*Merci de votre aide pour faire de MyDigitalTwin un projet d'ingénierie de données exemplaire !*