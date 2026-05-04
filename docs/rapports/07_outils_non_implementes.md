# Outils MLOps évalués et non implémentés

_Phase_ : 2G — Industrialisation & Qualité  
_Statut_ : ✅ Décision documentée

---

## Contexte

Dans le cadre de la phase d'industrialisation du projet MyDigitalTwin, trois outils MLOps/DataOps ont été évalués : **DVC**, **dlt (data load tool)** et **Kedro**. Chacun a été écarté après analyse de l'adéquation avec les contraintes réelles du projet.

---

## DVC (Data Version Control)

### Ce que DVC apporte
DVC est un système de versioning pour les données et les modèles ML. Il permet de tracer les artefacts (datasets, modèles) en dehors de Git, de reproduire des pipelines, et de gérer des expériences ML.

### Pourquoi non implémenté

**1. Le warehouse est déjà versionné par Delta Lake.**  
Delta Lake conserve nativement un log de transactions (`_delta_log/`) qui constitue un historique complet de chaque écriture. Ajouter DVC créerait une double couche de versioning redondante sur les mêmes fichiers.

**2. Les données sources ne bougent pas.**  
Les exports de plateformes (Instagram, Spotify, Netflix…) sont des snapshots ponctuels fournis par l'utilisateur. Il n'y a pas de pipeline continu à rejouer ni de dataset qui évolue quotidiennement — DVC est optimisé pour ce cas d'usage.

**3. Pas de modèles ML à versionner.**  
Les modèles utilisés (BLIP-2, OpenCLIP, ALS) sont des modèles pré-entraînés chargés depuis HuggingFace ou Spark MLlib. Aucun modèle entraîné sur les données du projet n'est persisté — il n'y a rien à "versionner".

**4. Overhead pour un projet solo.**  
DVC requiert un remote storage (S3, GCS, Azure…) et une discipline de `dvc add / dvc push` à chaque modification de données. Pour un projet personnel à exécution manuelle, ce coût opérationnel n'est pas justifié.

**Conclusion** : DVC serait pertinent si le projet évoluait vers un entraînement de modèles custom sur les données personnelles (fine-tuning d'un LLM sur le style d'écriture, par exemple). Dans l'état actuel, Delta Lake couvre le besoin.

---

## dlt (data load tool)

### Ce que dlt apporte
dlt est une librairie Python pour construire des pipelines de chargement de données. Elle offre l'inférence de schéma automatique, le chargement incrémental natif, et des connecteurs vers de nombreuses sources (REST APIs, JSON, bases de données) et destinations (DuckDB, BigQuery, Snowflake…).

### Pourquoi non implémenté

**1. Delta Lake n'est pas une destination supportée nativement.**  
dlt supporte DuckDB, BigQuery, Redshift, Snowflake, PostgreSQL, etc. — mais pas Delta Lake. L'utiliser imposerait soit de migrer toute la stack vers DuckDB, soit d'écrire un custom destination connector, ce qui représente plus de travail que le problème qu'il résout.

**2. Le chargement incrémental est déjà couvert.**  
La phase 2G a implémenté le pattern MERGE INTO Delta Lake dans tous les notebooks d'ingestion. Ce pattern offre exactement ce que dlt appelle "incremental loading" — les données existantes ne sont pas dupliquées, seules les nouvelles lignes sont insérées.

**3. Les sources sont des fichiers locaux, pas des APIs.**  
dlt apporte le plus de valeur sur des sources dynamiques (APIs REST avec pagination, webhooks, bases de données en streaming). Les sources de ce projet sont des exports JSON/ZIP statiques fournis manuellement par l'utilisateur — un simple `spark.read.json()` suffit.

**Quand dlt deviendrait pertinent** : si le projet évoluait vers une connexion directe aux APIs officielles (Spotify Web API, Instagram Graph API, Twitter API v2) pour une ingestion continue et automatisée. Dans ce cas, dlt + son incremental loading remplacerait avantageusement les notebooks d'ingestion.

---

## Kedro

### Ce que Kedro apporte
Kedro est un framework de data pipelines pour Python. Il impose une structure de projet standardisée, un Data Catalog déclaratif, un DAG de nœuds (`node`) et de pipelines, ainsi que des hooks et un système de versioning des runs.

### Pourquoi non implémenté

**1. Le projet n'a pas de pipeline continu à orchestrer.**  
Les notebooks d'ingestion sont exécutés manuellement une fois par plateforme, lors de l'import des données. Il n'existe pas de pipeline quotidien ou hebdomadaire à scheduler et monitorer — le principal cas d'usage de Kedro.

**2. Migrer les notebooks vers des nodes Kedro serait un refactoring massif à coût zéro.**  
Kedro impose de transformer chaque étape de traitement en une fonction Python pure (`node`), de déclarer chaque dataset dans un `catalog.yml`, et de connecter les nœuds en pipeline. Adapter les 30+ notebooks existants représente plusieurs jours de travail pour un résultat fonctionnellement identique.

**3. Le Data Catalog est redondant avec Delta Lake.**  
Le Data Catalog de Kedro gère les chemins et formats des datasets. Delta Lake + `config.py` remplissent déjà ce rôle de manière cohérente avec le reste de la stack (PySpark, Dash).

**4. La structure Kedro est inadaptée à un projet solo de data exploration.**  
Kedro est conçu pour des équipes qui ont besoin de standardisation, de reproductibilité inter-développeurs et de CI/CD sur les pipelines. Pour un projet personnel, cette structure ajoute de la complexité sans bénéfice collaboratif.

**Conclusion** : Kedro serait justifié si le projet devenait un service en production avec des pipelines planifiés, plusieurs contributeurs, et un besoin de reproductibilité stricte des runs. En l'état, la complexité introduite est injustifiée.

---

## Synthèse

| Outil | Problème ciblé | Couvert par | Verdict |
|-------|---------------|-------------|---------|
| DVC | Versioning données & modèles | Delta Lake (`_delta_log`) | ❌ Redondant |
| dlt | Chargement incrémental + connecteurs | MERGE INTO Delta Lake | ❌ Stack incompatible |
| Kedro | Orchestration & standardisation pipelines | Notebooks manuels suffisants | ❌ Sur-ingénierie |

Ces trois outils restent des candidats valides si le projet évolue vers une architecture de production avec ingestion continue, entraînement de modèles custom, ou collaboration multi-développeurs.
