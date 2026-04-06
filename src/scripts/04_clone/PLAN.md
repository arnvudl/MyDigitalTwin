# AXE 1 — Clone Conversationnel
_Priorité : moyenne — données à préparer manuellement_

---

## Objectif

Un chatbot qui **parle comme Arnaud** : même vocabulaire, même registre, mêmes références culturelles, même humour.

---

## Contrainte matérielle

**8 Go VRAM → fine-tuning LLM exclu.**

Même en QLoRA (quantification 4-bit), un Mistral-7B nécessite ~12–16 Go pour l'entraînement.  
Phi-3-mini (3.8B) serait faisable mais le résultat serait trop limité.

**Approche retenue : RAG-style prompt injection.**

---

## Approche RAG (Retrieval-Augmented Generation)

Construire une **mémoire personnelle** d'Arnaud depuis ses données texte, puis l'injecter dans le contexte d'un LLM (Claude ou Mistral local via Ollama).

```
Données texte → extraction style + lexique + exemples de réponses
        ↓
Base vectorielle (ChromaDB / FAISS)
        ↓
Query : "comment Arnaud répondrait à ce message ?"
        ↓
Retrieval : top-k exemples pertinents depuis la base
        ↓
Prompt enrichi → Claude API / Mistral Ollama
        ↓
Réponse "à la manière d'Arnaud"
```

---

## Données sources

| Source | Contenu | Valeur pour le clone |
|---|---|---|
| `twitter_tweets` | Tweets publics | Style d'écriture, humour, références |
| Instagram `post_comments_1.json` | Commentaires publics | Réactions courtes, emojis |
| Instagram `reels_comments.json` | Commentaires Reels | Même |
| Instagram DMs sélectionnés | Conversations privées | Registre informel, dynamiques |
| TikTok `ChatHistory` | Messages TikTok | Complémentaire |

**Sélection manuelle obligatoire pour les DMs** : uniquement les conversations avec des comportements intéressants (humour, émotions, ironie). Les autres participants sont anonymisés.

---

## Pipeline

```
01_extract_corpus.ipynb
  - Lecture tweets, commentaires, DMs sélectionnés
  - Nettoyage + anonymisation interlocuteurs
  - Export : warehouse/text_corpus.parquet
        ↓
02_style_analysis.ipynb  (PySpark — NLP axe 1 du plan ML)
  - Tokenizer + StopWordsRemover + NGram
  - Top n-grams, emojis favoris, longueur moyenne, ponctuation
  - Profil de style → style_profile.json
        ↓
03_clone_rag.ipynb / app
  - Embeddings des messages (sentence-transformers, local CPU)
  - Index FAISS ou ChromaDB
  - Fonction retrieval + prompt template
  - Interface dans /clone
```

---

## Prompt template

```
Tu es Arnaud, 22 ans, belge, étudiant en data science.
Voici des exemples de comment tu parles :
{exemples_retrieved}

Voici ton profil de style :
- Emojis favoris : {top_emojis}
- Expressions récurrentes : {top_ngrams}
- Registre : informel, direct, références musique/gaming/anime

Réponds au message suivant comme tu le ferais naturellement :
{message_utilisateur}
```

---

## Dashboard — page `/clone`

- Interface de chat simple
- Chaque réponse affiche les exemples ayant servi de base (transparence)
- Option : voir le "profil de style" (stats NLP)

---

## Considérations éthiques

- DMs sélectionnés **manuellement** — jamais automatiquement
- Interlocuteurs **anonymisés** dans le corpus
- Modèle et données restent **100% locaux**
- Données brutes dans `data/` (gitignore)

---

## Fichiers à créer

| Fichier | Contenu |
|---|---|
| `01_extract_corpus.ipynb` | Extraction + nettoyage texte |
| `02_style_analysis.ipynb` | NLP PySpark — profil style |
| `03_clone_rag.ipynb` | Construction index + retrieval |
| `app/pages/clone.py` | Interface chatbot dashboard |
