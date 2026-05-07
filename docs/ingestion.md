# Ingestion incrémentale

## Vue d'ensemble

Le pipeline d'ingestion comporte deux étapes indépendantes, chacune gérée différemment pour l'incrémental.

```
data/inbox/  →  [Parsers]  →  data/processed/<SOURCE>/  →  [Notebooks Spark]  →  data/warehouse/
```

---

## Étape 1 — inbox → processed (Parsers)

Les parsers déplacent les fichiers depuis `data/inbox/` vers `data/processed/`.
Le comportement dépend de la source :

| Source | OVERWRITE | Logique |
|---|---|---|
| Instagram | `False` | Exports cumulatifs. Un fichier déjà présent dans `processed/` n'est pas écrasé. Plusieurs exports peuvent être fusionnés. |
| Google Takeout | `False` | Idem. Plusieurs archives Takeout sont fusionnées. |
| Spotify | `False` | Idem. Distingue `account/` et `extended/` selon le nom du dossier inbox. |
| TikTok | `True` | Export monolithique (`user_data_tiktok.json`). Le plus récent remplace toujours. |
| Twitter/X | `True` | Archive complète. Le plus récent remplace toujours. |
| Netflix | `True` | Fichier CSV unique complet. Le plus récent remplace toujours. |

**Détection** : les parsers reconnaissent les exports par le préfixe du dossier
dans `inbox/` (`instagram*`, `takeout*`, `spotify*`, etc.). Netflix est
l'exception : le fichier doit s'appeler exactement `NetflixViewingHistory.csv`.

### Validation pré-ingestion

Avant de déplacer quoi que ce soit, chaque parser valide la structure de son
dossier inbox :

- **Hard fail** : dossier détecté mais vide → exception, source marquée `error`
  dans le log, pipeline des autres sources non interrompu
- **Warning** : extensions inattendues → log de warning, déplacement quand même

---

## Étape 2 — processed → warehouse (Notebooks Spark)

Tous les notebooks utilisent le pattern **Delta Lake MERGE INTO** :

```python
DeltaTable.forPath(spark, path).alias("t")
    .merge(df.alias("s"), "t.<clé1> = s.<clé1> AND t.<clé2> = s.<clé2>")
    .whenNotMatchedInsertAll()
    .execute()
```

Seules les lignes absentes sont insérées. Le même notebook peut être relancé
10 fois sans créer de doublons. Les clés de merge sont définies par source :

| Table | Clé de merge |
|---|---|
| `spotify_streams` | `(artistName, trackName, listen_ts tronquée à la minute)` |
| `spotify_liked_songs` | `(trackUri)` |
| `instagram_comments` | `(text, timestamp)` |
| `instagram_messages_meta` | `(conv_id, sender, timestamp, msg_type)` |
| `netflix_views` | `(raw_title, watch_date)` |
| `google_searches` | `(query, timestamp_ms)` |
| `youtube_watch` | `(url, timestamp_ms)` |
| `tiktok_watch` | `(video_id, timestamp_ms)` |
| `twitter_tweets` | `(tweet_id)` |

---

## Ajouter un nouvel export

Workflow standard pour une source déjà supportée (ex : nouveau dump Spotify) :

1. Télécharger et dézipper l'export
2. Déposer le dossier dans `data/inbox/`
3. Lancer l'ingestion :
   ```bash
   docker compose exec spark-master python3 -m src.ingestion.run_all --sources spotify
   ```
4. Relancer les notebooks concernés dans `src/scripts/01_exploration/`

Le MERGE INTO garantit que seules les nouvelles écoutes/activités sont ajoutées.

---

## Conseil : garde une copie locale de tes exports

Les parsers **déplacent** (et non copient) les fichiers depuis `inbox/`.
Si l'ingestion est interrompue entre le déplacement et l'écriture warehouse
(crash Docker, coupure réseau, etc.), les fichiers ne sont plus dans `inbox/`
mais le warehouse n'a pas été mis à jour.

**La solution simple** : garde une copie de tes exports originaux sur ton disque,
en dehors du repo. Si quelque chose déraille, tu redéposes dans `inbox/` et tu
relances. Le MERGE INTO fait le reste sans créer de doublons.

---

## Observabilité

Après chaque exécution de `run_all`, trois artefacts sont mis à jour :

### `data/ingestion_log.json`

Statut complet par source :

```json
{
  "last_run": "2026-05-07T10:00:00",
  "sources": {
    "spotify": {
      "last_run":    "2026-05-07T10:00:00",
      "status":      "ok",
      "files_moved": 3,
      "duration_s":  0.8,
      "error":       null
    },
    "netflix": {
      "last_run":    "2026-05-07T10:00:00",
      "status":      "skip",
      "files_moved": 0,
      "duration_s":  0.0,
      "error":       null
    }
  }
}
```

Valeurs possibles pour `status` : `ok`, `skip` (aucun fichier inbox détecté),
`error` (exception levée).

### `data/logs/ingestion_YYYY-MM-DD.log`

Log structuré complet avec timestamps, niveau (`DEBUG` / `INFO` / `WARNING` /
`ERROR`) et nom du logger. Utile pour déboguer un problème de parsing ou de
déplacement de fichiers.

### `data/alerts.json`

Créé (ou mis à jour) uniquement quand au moins une source est en erreur.
Contient un historique cumulatif des erreurs avec timestamp et message.

```json
[
  {
    "timestamp": "2026-05-07T10:00:00",
    "errors": {
      "google": {
        "status":     "error",
        "files_moved": 0,
        "duration_s": 0.1,
        "error":      "Dossier inbox vide : data/inbox/takeout-2026-05-07"
      }
    }
  }
]
```

Ces trois fichiers sont ignorés par Git (`.gitignore`).
