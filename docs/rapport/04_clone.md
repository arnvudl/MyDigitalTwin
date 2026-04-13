# Phase 04 — Clone Conversationnel (Le Sage)

_Dossier_ : `src/scripts/04_clone/`  
_Statut_ : 🔜 En cours (V5 RAG)  
_Scripts_ : `01_extract_corpus.py`, `02_convert_chatml.py`, `03_finetune_runpod/`, `05_export_for_gemini.py`  
_Historique complet_ : `src/scripts/04_clone/STATUS.md`

---

## Objectif

Un clone conversationnel qui parle nativement comme Arnaud — vocabulaire, rythme, minimalisme, tics de langage — accessible depuis la page `/clone` du dashboard.

---

## Historique des versions

| Version | Résultat |
|---|---|
| V1 | Overfitting massif, réponses par cœur |
| V2 | Overfitting dès epoch 2-3, loss chute à 0.55 |
| V3 | ✅ Style OK — cohérence conversationnelle ❌ |
| V4 | ❌ Abandonnée → pivot vers RAG |
| **V5** | **🚀 En cours — RAG + Gemini 1.5 Flash** |

---

## Ce qui a été essayé : Fine-tuning QLoRA (V1 → V3)

### Choix QLoRA

Un fine-tuning complet (toutes les couches) sur un modèle 7B nécessite ~80 Go VRAM. **QLoRA** (Quantized Low-Rank Adaptation) :
- Modèle chargé en 4 bits → ~4 Go VRAM
- Seules des matrices d'adaptation de faible rang sont entraînées
- Fine-tuning possible sur RTX 3090/4090 (24 Go VRAM) loué ~0.50$/h sur RunPod

### Ce qui a fonctionné en V3

- 1 epoch sur 8 734 exemples → loss finale **0.088** (parfait, pas d'overfitting)
- Modèle de base : Mistral 7B Instruct v0.3 avec QLoRA
- Export GGUF Q4_K_M (~4.1 Go) via [solution symlink RunPod](../../../src/scripts/04_clone/STATUS.md)
- **Le style était là** : le clone parlait comme Arnaud

### Leçon critique sur les epochs

> **1 epoch = parfait (loss ~0.088)**  
> **2 epochs = début d'overfitting**  
> **3 epochs = overfitting confirmé (mémorisation pure, loss ~0.55)**

### Problème bloquant de V3 : Mistral v0.3 et le system prompt

Mistral v0.3 n'a pas de token `<|system|>` dédié. Le system prompt est collé dans le premier `[INST]` sans séparation claire → il se noie dans le contexte → le clone hallucine ou répond de façon incohérente sur qui il est, malgré un bon style.

---

## Pourquoi le Fine-tuning a été abandonné

Deux problèmes fondamentaux persistent même après correction du modèle de base :

1. **Hallucinations** : Le modèle mélange ses connaissances générales avec les données d'entraînement → invente des faits sur Arnaud.
2. **Maintenance** : Chaque mise à jour du corpus (nouveaux messages) = nouvel entraînement complet (RunPod + temps + export GGUF). Pas viable.

---

## Approche retenue : RAG + Gemini 1.5 Flash (V5)

### Principe

1. Le corpus (300 meilleurs exemples) est indexé avec `sentence-transformers` (`all-MiniLM-L6-v2`).
2. À chaque message, les **3 exemples de style les plus proches** sont récupérés par recherche sémantique.
3. Gemini reçoit : `System Prompt` + `Exemples RAG` + `Historique récent` + `Message actuel`.

### Pourquoi RAG est meilleur ici

| Critère | Fine-tuning | RAG + Gemini |
|---|---|---|
| Hallucinations | ❌ Fréquentes | ✅ Ancrées dans les exemples réels |
| Style | ✅ Parfait | ✅ Parfait (exemples injectés dynamiquement) |
| Coût inférence | GPU local ou loué | ✅ Gratuit (Gemini Flash) |
| Mise à jour corpus | ❌ Réentraînement complet | ✅ Régénérer `gemini_corpus.txt` |
| Fenêtre de contexte | Limitée | ✅ 1M tokens |

### Pourquoi Gemini 1.5 Flash ?

- Gratuit dans les limites API actuelles.
- Fenêtre de contexte 1M tokens : peut absorber tout le corpus + historique.
- Latence faible (Flash) : adapté au chat temps réel.
- `05_export_for_gemini.py` prépare le corpus dans le format attendu.

---

## Préparation du Corpus

### Philosophie "Qualité > Quantité"

500 paires parfaites > 10 000 messages bruités. Ce qui fait la valeur du corpus :
- **Minimalisme** : "bah", "jsp", "oe", "t ou" — signature rythmique d'Arnaud
- Absence de majuscules, ponctuation atypique
- Tics de langage, registre oral
- Séquences de courts messages (pas de gros blocs)

### Ce qui est filtré

- Messages purement techniques : "Photo envoyée", "Appel manqué"
- Informations sensibles
- Doublons massifs

**Voir** : `docs/selection_corpus_clone.md` pour le guide complet de sélection.

---

## Ce qui reste à faire

- [ ] Finaliser l'indexation RAG (FAISS ou cosine similarity simple)
- [ ] Connecter `/clone` du dashboard à l'API Gemini + RAG
- [ ] Tester la cohérence conversationnelle en V5
