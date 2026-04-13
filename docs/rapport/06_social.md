# Phase 06 — Graphe Social Instagram

_Dossier_ : `src/scripts/06_social/`  
_Statut_ : ✅ Terminé  
_Notebook_ : `01_social_graph.ipynb`  
_Output_ : `data/warehouse/social_graph.parquet`

---

## Objectif

Construire un graphe de relations sociales à partir des conversations Instagram (DMs), pondéré par l'intensité des échanges et le statut "proche".

---

## Pourquoi Pandas et non Spark ?

Cette phase est délibérément en **Pandas pur** — sans Spark. Justification :

- Les données d'entrée sont des **fichiers JSON par conversation**, lus individuellement depuis `data/raw/INSTAGRAM/messages/inbox/`. Ce n'est pas un DataFrame tabular à lire en bulk.
- Le volume de nœuds est faible (~100 conversations max après filtre).
- Le traitement est séquentiel par nature (parser conversation → accumuler stats).

Utiliser Spark ici aurait été de la sur-ingénierie (`sparkContext.wholeTextFiles()` pour parser du JSON imbriqué, vs une simple boucle Python).

---

## Construction du Graphe

### Structure

Le graphe est **non dirigé, pondéré** : un nœud = une personne, une arête = la relation avec Arnaud, poids = volume d'échanges normalisé.

### Pondération

```python
weight = message_count * 2.0   # si close friend
weight = message_count * 1.0   # sinon
```

Le multiplicateur `CLOSE_FRIENDS_MULTIPLIER = 2.0` booste les liens avec les amis proches, pour que le graphe reflète la **qualité** des relations et pas uniquement le volume brut.

### Filtre : `MIN_MESSAGES = 5`

Seuil pour exclure les conversations ponctuelles (bots, inconnus, contacts one-shot). Sans ce filtre, le graphe contiendrait des centaines de nœuds parasites.

### Gestion des noms

Les dossiers Instagram ont le format `prenom_1234567890`. Le prénom est extrait via regex `re.split(r'_\d{10,}', folder)[0].lower()`. Le matching avec `CLOSE_FRIENDS` (set de prénoms) est fait sur ce prénom extrait.

---

## Visualisation (Dashboard)

Le graphe est visualisé via **Cytoscape.js** dans la page `/social`. Les nœuds sont dimensionnés proportionnellement au poids (volume de messages), et les close friends sont mis en évidence par une couleur distincte.

---

## Décision : données Instagram uniquement

On aurait pu inclure TikTok et Twitter DMs. Choix de se limiter à Instagram :
- Instagram = réseau social principal avec le plus de conversations réelles.
- TikTok DMs : très peu de conversations privées (principalement du scroll, pas du messaging).
- Twitter DMs : faible volume + contacts souvent des inconnus/marques.
