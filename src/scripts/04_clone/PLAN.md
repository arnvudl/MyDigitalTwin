# AXE 1 — Clone Conversationnel
_Priorité : haute — dataset prêt, fine-tuning à lancer_

---

## Objectif

Un chatbot qui **parle comme Arnaud** : même vocabulaire, même registre, mêmes références culturelles, même humour.

---

## Contrainte matérielle

**8 Go VRAM → fine-tuning local exclu.**

**Approche retenue : fine-tuning cloud (RunPod / Vast.ai) + inférence locale.**

- Fine-tuning QLoRA sur RunPod (~1-2h, < $5)
- Modèle base : **Mistral 7B Instruct** (meilleur français, tourne en Q4_K_M sur 8Go VRAM)
- Inférence locale via **Ollama**
- Framework recommandé : **Unsloth** (plus rapide que HuggingFace pour QLoRA)

---

## Données sources

**21 conversations Instagram DM** sélectionnées — personnes avec qui Arnaud est lui-même.  
Convos riches (250 ex) : Alice, Nana, Lou, Maelle  
Convos standard (100-300 ex) : Djyoyo, Evan, Pilou, Laura, Jen, Loulou, Laure, Gabi, Mylene, Manonvandy, Fafie, Ama, Eliott, Paulina, Celia, Vic, Romane

**Score de sélection calibré** sur 62k messages réels d'Arnaud (marqueurs slang, raisonnement, curiosité, rythme multi-messages).

---

## Pipeline

```
01_extract_corpus.py        [DONE]
  - Sliding window (70 msgs, step 35) sur 21 convos Instagram
  - Scoring calibré sur style réel d'Arnaud
  - Sampling temporel stratifié (couvre debut->fin de chaque conv)
  - Fusion avec sélections manuelles (CONV_BIG_DATA/)
  - Export : data/LLM_DATA/dataset_final.jsonl (6363 exemples)
        |
        v
02_convert_chatml.py        [DONE]
  - System prompt complet (personnalité, style, expressions)
  - Conversion au format ChatML (human/gpt)
  - Split train (95%) / val (5%)
  - Export : data/LLM_DATA/train.jsonl + val.jsonl (6341 exemples)
        |
        v
03_finetune_runpod/          [TODO]
  - Config Unsloth pour Mistral 7B QLoRA
  - Lancement sur RunPod
  - Récupération des poids LoRA
        |
        v
04_deploy_local/             [TODO]
  - Fusion poids LoRA + modèle base
  - Export GGUF pour Ollama
  - Test local
        |
        v
app/pages/clone.py           [TODO]
  - Interface chatbot dans le dashboard
```

---

## System Prompt (dans 02_convert_chatml.py)

Construit sur analyse statistique de 62k messages. Couvre :
- Identité (HPI, belge, data science, 22 ans)
- Personnalité (philosophe, psy naturel, curieux, s'énerve vite)
- Passions (musique, films Nolan/Spielberg, voyages, volley)
- Style d'écriture (slang, peu d'emojis, multi-messages, signatures uniques)

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

## Fichiers

| Fichier | Statut | Contenu |
|---|---|---|
| `01_extract_corpus.py` | **DONE** | Extraction + scoring + fusion dataset |
| `02_convert_chatml.py` | **DONE** | Conversion ChatML + system prompt + split train/val |
| `03_finetune_runpod/` | TODO | Config Unsloth + instructions RunPod |
| `04_deploy_local/` | TODO | Export GGUF + config Ollama |
| `app/pages/clone.py` | TODO | Interface chatbot dashboard |

## Données générées

| Fichier | Contenu |
|---|---|
| `data/LLM_DATA/dataset_final.jsonl` | 6363 exemples fusionnés (auto + manuel) |
| `data/LLM_DATA/dataset_chatml.jsonl` | 6341 exemples format ChatML |
| `data/LLM_DATA/train.jsonl` | 6023 exemples (95%) |
| `data/LLM_DATA/val.jsonl` | 318 exemples (5%) |
