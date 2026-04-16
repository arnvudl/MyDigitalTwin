# Phase 06 — Graphe Social Instagram

_Dossier_ : `src/scripts/06_social/`  
_Statut_ : ✅ Terminé  
_Notebook_ : `01_social_graph.ipynb`  
_Output_ : `data/warehouse/social_graph/` (dossier parquet)

---

## Objectif

Construire un graphe de relations sociales à partir des conversations Instagram (DMs), pondéré par l'intensité des échanges et le statut "proche", et le visualiser en 3D dans la page `/social` du dashboard.

---

## Pourquoi Pandas et non Spark ?

Cette phase est délibérément en **Pandas pur** — sans Spark. Justification :

- Les données d'entrée sont des **fichiers JSON individuels par conversation**, lus séquentiellement depuis `data/raw/INSTAGRAM/messages/inbox/`. Ce n'est pas un DataFrame tabular à lire en bulk — chaque conversation est un dossier contenant un ou plusieurs `message_*.json`.
- Le volume de nœuds est faible (~100 conversations max après filtre).
- Le parsing est séquentiel par nature (parcourir les dossiers → accumuler les stats).

Utiliser Spark ici aurait été de la sur-ingénierie (`sparkContext.wholeTextFiles()` pour parser du JSON imbriqué, vs une simple boucle Python).

---

## Structure des données Instagram

Instagram exporte les DMs comme suit :

```
inbox/
  prenom_1234567890/          ← dossier par conversation (pseudo + timestamp)
    message_1.json            ← messages paginés à 10 000 msgs/fichier
    message_2.json
    ...
```

Chaque `message_*.json` contient :
- `participants` : liste des participants (2 pour un DM, >2 pour un groupe)
- `messages` : liste de messages avec `content`, `sender_name`, `timestamp_ms`

---

## Construction du Graphe

### Structure

Le graphe est **non dirigé, pondéré** : un nœud = une personne, une arête = la relation avec Arnaud, poids = volume d'échanges normalisé.

### Parsing multi-fichiers

Une conversation peut s'étendre sur plusieurs fichiers (cap à 10 000 messages par fichier). `_parse_conversation` les somme tous :

```python
msg_count = 0
for fname in msg_files:
    with open(fname) as f:
        msg_count += len(json.load(f).get("messages", []))
```

Seules les conversations **1-to-1** sont retenues (`len(participants) == 2`).

### Filtre : `MIN_MESSAGES = 5`

Seuil pour exclure :
- Bots et spams (souvent 1-2 messages)
- Contacts one-shot (demandes ponctuelles, inconnus)
- Groupes (filtrés avant par le critère participants==2)

Sans ce filtre, le graphe contiendrait des centaines de nœuds parasites sur ~400 conversations total.

### Extraction du prénom

Les dossiers Instagram ont le format `prenom_1234567890` (pseudo + timestamp d'export). Le prénom est extrait via regex :

```python
label = re.split(r'_\d{10,}', folder)[0].lower()
```

Le matching avec `CLOSE_FRIENDS` (set de prénoms défini dans `config.py`) est fait sur ce prénom extrait, ou sur le `node_id` complet en fallback.

### Pondération

```python
weight = message_count * CLOSE_FRIENDS_MULTIPLIER   # si close friend (défaut ×2.0)
weight = message_count                              # sinon
```

Le multiplicateur `CLOSE_FRIENDS_MULTIPLIER = 2.0` booste les liens avec les amis proches pour que le graphe reflète la **qualité** des relations et pas uniquement le volume brut. Dans la visualisation, ce poids détermine la taille des nœuds et l'épaisseur des arêtes.

---

## Sauvegarde — format dossier parquet

```python
out_dir = os.path.join(WAREHOUSE, "social_graph")
df.to_parquet(os.path.join(out_dir, "part-0.parquet"), index=False)
```

Le fichier est sauvegardé dans un **dossier** (pas un fichier `.parquet` unique), cohérent avec le pattern des autres tables warehouse lues par le dashboard :

```
data/warehouse/
  social_graph/
    part-0.parquet    ← 128 lignes
  spotify_streams/    ← même format
  netflix_views/
  ...
```

Le dashboard lit depuis ce dossier via `pd.read_parquet(directory)` — pyarrow gère nativement la lecture de dossiers parquet.

---

## Dashboard — `/social`

### Lecture des données

```python
def _load():
    files = [f for f in os.listdir(SOCIAL_DIR) if f.endswith(".parquet")]
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
```

Même pattern que `_read_delta()` dans les autres pages — lecture depuis le dossier, concaténation des fichiers parquet.

### Visualisation 3D (3d-force-graph)

Le graphe est rendu via **3d-force-graph.js** dans un Iframe. Le layout est calculé côté serveur au chargement de la page (`layout()`) :

1. `_load()` → DataFrame pandas (128 nœuds)
2. `_conv_stats()` → stats par nœud depuis les JSON bruts (sent/received, dates, messages récents)
3. `_df_to_graph_data()` → conversion en `{nodes, links}` JSON pour 3d-force-graph
4. `_build_3d_html()` → génération HTML+JS injecté dans `assets/social_3d.html`
5. Dashboard → `<Iframe src="/assets/social_3d.html">`

### Encodage Instagram (mojibake)

Les JSON Instagram sont encodés en latin-1 réinterprété en UTF-8. La fonction `_fix_encoding` corrige le mojibake sur les noms et contenus :

```python
def _fix_encoding(text):
    return text.encode("latin-1").decode("utf-8")
```

### Taille des nœuds

```python
# Close friends : nœuds plus grands (20–64), arêtes épaisses (violet)
val = int(20 + 44 * ratio)   # si close friend
# Followers : nœuds petits (1–12), arêtes fines (bleu)
val = int(1  + 11 * ratio)   # sinon
```

`ratio = message_count / max_message_count` — normalisation pour que le nœud le plus actif ait la valeur maximale.

---

## Décision : données Instagram uniquement

On aurait pu inclure TikTok et Twitter DMs. Choix de se limiter à Instagram :
- Instagram = réseau social principal avec le plus de conversations réelles.
- TikTok DMs : très peu de conversations privées (principalement du scroll, pas du messaging).
- Twitter DMs : faible volume + contacts souvent des inconnus/marques.

---

## Résultats

- **402 conversations** dans l'inbox
- **128 conversations** retenues (>= 5 messages)
- **29 close friends** identifiés
- **267 499 messages** total
- Top relation : ~66 000 messages (7 ans de conversation)
