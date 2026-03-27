# MyDigitalTwin — Plan Machine Learning & Sources de données

## Architecture cible

Toutes les sources sont lues directement en PySpark et converties en **Parquet** avant toute analyse ML.

```
data/raw/          ← fichiers bruts originaux (jamais modifiés)
data/parquet/      ← datasets nettoyés en Parquet (entrée des notebooks ML)
notebooks/         ← notebooks PySpark (exploration + ML)
```

---

## Sources de données par axe ML

---

### 1. Le "Clone" — NLP & Style personnel

> *Extraire mes n-grams, mon vocabulaire, mes emojis favoris pour modéliser mon style d'écriture.*

| Fichier source | Plateforme | Format | Contenu utile |
|---|---|---|---|
| `your_instagram_activity/comments/post_comments_1.json` | Instagram | JSON | Tes commentaires publics |
| `your_instagram_activity/comments/reels_comments.json` | Instagram | JSON | Tes commentaires Reels |
| `your_instagram_activity/messages/inbox/*/message_*.json` | Instagram | JSON | Texte de tes DMs (métadonnées + longueur) |
| `data/tweets.js` | Twitter/X | JS | Tes tweets (texte complet) |
| `data/Direct Message/Direct Messages/ChatHistory` | TikTok | JSON | Tes messages TikTok |

**Output Parquet** : `text_corpus.parquet`
```
user_text | platform | timestamp | char_count | word_count | emoji_count | lang
```

**PySpark ML** :
- `Tokenizer` + `StopWordsRemover` + `NGram` (bigrammes/trigrammes)
- `CountVectorizer` → matrice TF-IDF de ton vocabulaire
- Extraction emoji via regex

---

### 2. L'Oracle des Recommandations — ALS

> *Modéliser mes goûts pour prédire quel contenu me fera réagir.*

| Fichier source | Plateforme | Format | Contenu utile |
|---|---|---|---|
| `NetflixViewingHistory.csv` | Netflix | CSV | Titres regardés + dates |
| `your_instagram_activity/likes/liked_posts.json` | Instagram | JSON | Posts likés (timestamps) |
| `your_instagram_activity/saved/saved_posts.json` | Instagram | JSON | Posts sauvegardés (intérêt fort) |
| `Your Orders/Your Amazon Orders/Order History.csv` | Amazon | CSV | Achats par catégorie |
| `Your Orders/Your Amazon Orders/Digital Content Orders.csv` | Amazon | CSV | Achats digitaux (films, livres) |
| `Activity/Watch History/VideoList` | TikTok | JSON (dans user_data) | Vidéos regardées |
| `Activity/Like List/ItemFavoriteList` | TikTok | JSON (dans user_data) | Vidéos likées |
| `Your Activity/Ad Interests/AdInterestCategories` | TikTok | JSON (dans user_data) | Centres d'intérêt détectés |
| `data/like.js` | Twitter/X | JS | Tweets likés |
| *Données Spotify à venir* | Spotify | JSON | Historique d'écoute, playlists |

**Output Parquet** : `interactions.parquet`
```
item_id | item_title | item_category | platform | action_type | timestamp | weight
```
*(weight : 1=vu, 2=liké, 3=sauvegardé/acheté)*

**PySpark ML** :
- `ALS` (Alternating Least Squares) de `pyspark.ml.recommendation`
- Catégorisation Netflix par genre (via titre → lookup TMDB API)

---

### 3. Le Dashboard des "Moi" — K-Means Clustering

> *Regrouper mes activités en profils comportementaux : Étudiant, Loisirs, Nuit, Shopping...*

| Fichier source | Plateforme | Format | Contenu utile |
|---|---|---|---|
| `Your Orders/Your Amazon Orders/Order History.csv` | Amazon | CSV | Montants, catégories, dates |
| `Mon activité chez Google/Recherche/MonActivité.html` | Google | HTML | Requêtes de recherche + timestamps |
| `Mon activité chez Google/Chrome/MonActivité.html` | Google | HTML | Navigation + timestamps |
| `historique youtube (2023 - now)/watch-history.html` | YouTube | HTML | Vidéos regardées + timestamps |
| `AppInstallActivity/App Install Activity.csv` | Apple | CSV | Apps utilisées + dates |
| `your_instagram_activity/likes/liked_posts.json` | Instagram | JSON | Activité par heure/jour |
| `your_instagram_activity/messages/inbox/*/message_*.json` | Instagram | JSON | Activité temporelle (métadonnées) |
| `Extraits de compte Belfius (×4 PDF)` | Belfius | PDF | Dépenses par catégorie + dates |
| *Données Spotify à venir* | Spotify | JSON | Genres musicaux + moments d'écoute |

**Output Parquet** : `activity_vectors.parquet`
```
timestamp | hour | weekday | platform | category | amount | activity_type
```

**PySpark ML** :
- `VectorAssembler` → features numériques (heure, jour, montant, catégorie encodée)
- `KMeans` avec k=5-8 clusters
- `PCA` pour visualisation 2D de la "galaxie de profils"

---

## Données supplémentaires identifiées

### Netflix — `NetflixViewingHistory.csv`
Structure simple : `Title, Date`
- Deux colonnes, des milliers de lignes
- Extraction série/saison/épisode via regex sur le titre
- À enrichir avec l'API TMDB pour avoir les genres

### Belfius (4 PDFs)
- Parser via `pdfplumber` ou `tabula` en PySpark
- Extraction : date, montant, description, catégorie
- Anonymisation des bénéficiaires (remplacés par catégorie)

### Spotify (en attente)
Fichiers attendus dans l'export :
- `StreamingHistory_music_*.json` → historique d'écoute (artiste, titre, ms_played)
- `YourLibrary.json` → playlists, artistes suivis
- `Inferences.json` → centres d'intérêt détectés par Spotify

---

## Fichiers ignorés (non pertinents pour le ML)

| Fichier | Raison |
|---|---|
| `Apple Pay Cards.csv` / `Apple Card User Information.csv` | Données bancaires sensibles |
| `Apple ID SignOn Information.csv` | Logs de connexion, pas analytique |
| `Passkeys Information.csv` | Sécurité |
| `data/ip-audit.js` (Twitter) | Logs IP, pas analytique |
| `data/periscope-*.js` (Twitter) | Service arrêté |
| `Retail.TransactionalInvoicing.*.pdf` (Amazon) | Factures, redondant avec Order History |
| `media/` (Instagram photos/vidéos) | Médias → traitement séparé (métadonnées uniquement) |
| `Gmail/MonActivité.html` | Trop personnel |

---

## Pipeline PySpark global

```
Notebook 01 — Ingestion & nettoyage
    └── Lecture raw → anonymisation → écriture Parquet

Notebook 02 — Exploration (EDA)
    └── Stats descriptives, distributions, corrélations

Notebook 03 — NLP & Clone (ML axe 1)
    └── Tokenization → TF-IDF → N-grams → profil style

Notebook 04 — Recommandations ALS (ML axe 2)
    └── Matrice interactions → ALS → top recommandations

Notebook 05 — Clustering K-Means (ML axe 3)
    └── Feature engineering → KMeans → PCA → galaxie

Notebook 06 — Dashboard (visualisation)
    └── Export résultats → dashboard interactif
```

---

*Document MyDigitalTwin — mis à jour au 27/03/2026*
*Sources manquantes : Spotify (en attente d'export)*