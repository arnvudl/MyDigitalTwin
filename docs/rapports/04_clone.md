# Phase 04 — Clone Conversationnel (Le Sage)

_Dossier_ : `src/scripts/04_clone/`  
_Statut_ : ✅ V6 déployée (Gemini Flash — corpus injecté)  
_Scripts_ : `01_extract_corpus.py`, `02_build_gemini_corpus.py`  
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
| V4 | ❌ Abandonnée → pivot vers Gemini |
| V5 RAG | ❌ Abandonnée → RAG inutile (corpus rentre dans la fenêtre) |
| **V6** | **✅ Gemini Flash — system prompt + corpus injecté directement** |

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

## Approche retenue : Gemini Flash + corpus injecté (V6)

### Principe

Le corpus (300 meilleurs exemples scorés) et le system prompt sont injectés **en entier** dans chaque appel API — pas de RAG, pas de vector store. La fenêtre de contexte de Gemini Flash (~1M tokens) est suffisante pour absorber le corpus complet.

### Pourquoi pas de RAG ?

Le RAG n'apporte un gain que si le corpus dépasse la fenêtre de contexte. Ici (~50k tokens), il rentre largement → injection directe plus simple et plus efficace (cohérence de style globale vs retrieval thématique).

### Comparaison des approches

| Critère | Fine-tuning | RAG | **Gemini Direct (V6)** |
|---|---|---|---|
| Hallucinations | ❌ Fréquentes | ✅ Ancrées | ✅ Ancrées |
| Style | ✅ Parfait | ✅ Bon | ✅ Parfait |
| Coût inférence | GPU local/loué | Gratuit | Gratuit* |
| Mise à jour corpus | ❌ Réentraînement | ✅ Régénérer | ✅ Régénérer |
| Complexité | Haute | Moyenne | **Faible** |

_*Gratuit sous les limites du free tier Gemini (250k tokens/min). Voir limitation ci-dessous._

### ⚠️ Limitation connue : quota free tier

Le corpus injecté (~50k tokens) + historique conversation dépasse rapidement la limite **250k tokens/minute** du free tier Gemini 2.5 Flash.

**Si quota dépassé** : remplacer Gemini par **Groq** (vraiment gratuit, `llama-3.3-70b`) et réduire `TOP_N` dans `02_build_gemini_corpus.py` de 300 → 50-100 exemples.

---

## Pipeline final

```
01_extract_corpus.py       → data/LLM_DATA/dataset_final.jsonl
02_build_gemini_corpus.py  → data/LLM_DATA/gemini_corpus.txt + gemini_system.txt
app/pages/clone.py         → API Gemini Flash (system + corpus + historique)
```

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
