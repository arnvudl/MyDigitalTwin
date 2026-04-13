# Status — Clone Conversationnel (Le Sage)

**Dernière mise à jour** : 2026-04-12

---

## Historique des versions

| Version | Statut | Résultat |
|---|---|---|
| V1 | Terminée | Overfitting massif, réponses par cœur |
| V2 | Terminée | Overfitting à epoch 2-3, loss chute à 0.55 |
| V3 | **✅ Terminée** | Style ✅, cohérence conversationnelle ❌ (sans system prompt dans base model) |
| V4 | ❌ Abandonnée | Remplacée par approche RAG (plus flexible et performante) |
| **V5** | **🚀 En cours** | **Pivot vers RAG + Gemini 1.5 Flash** |

---

## V5 — Pivot RAG (Retrieval-Augmented Generation) 🚀

### Pourquoi abandonner le Fine-Tuning ?
Malgré des résultats stylistiques intéressants en V3, le fine-tuning souffre de deux problèmes majeurs :
1. **Hallucinations** : Le modèle invente des faits car il mélange ses connaissances de base avec les données de l'entraînement.
2. **Maintenance** : Chaque mise à jour du dataset demande un nouvel entraînement coûteux (RunPod, temps, export GGUF).

### Nouvelle Stratégie : Gemini 1.5 Flash + RAG
On utilise la puissance de **Gemini 1.5 Flash** (gratuit, rapide, énorme fenêtre de contexte) couplée à une recherche sémantique locale.

- **Moteur RAG** : Utilisation de `sentence-transformers` (`all-MiniLM-L6-v2`) pour indexer le corpus.
- **Corpus** : 300 meilleurs exemples de conversations (extraits par `05_export_for_gemini.py`).
- **Fonctionnement** : 
    1. L'utilisateur envoie un message.
    2. Le système cherche les 3 exemples les plus proches dans le corpus (style matching).
    3. Gemini reçoit : `System Prompt (Identité)` + `Exemples de style (RAG)` + `Historique récent` + `Message actuel`.

### Avantages de la V5
- **Zéro Hallucination** : Le modèle reste ancré dans les exemples fournis.
- **Style parfait** : Gemini imite les exemples de dialogues réels injectés dynamiquement.
- **Gratuité & Vitesse** : Pas besoin de GPU local ou de location RunPod pour l'inférence.
- **Mise à jour instantanée** : Il suffit de régénérer `gemini_corpus.txt` pour mettre à jour la "mémoire" du clone.

---

## V3 — Ce qui a été fait ✅


- [x] Fine-tuning **1 epoch** sur 8 734 exemples → loss stabilisée à **0.088** (parfait, pas d'overfitting)
- [x] LoRA sauvegardé : `/workspace/work/arnaud-clone-lora` (~1.3 Go) sur Volume Persistant RunPod
- [x] Export GGUF `Q4_K_M` réussi : `mistral-7b-instruct-v0.3.Q4_K_M.gguf` (~4.1 Go)
- [x] GGUF téléchargé localement : `data/LLM_DATA/mistral-7b-instruct-v0.3.Q4_K_M.gguf`
- [x] Modèle Ollama créé : `arnaud-sage`

### Leçon apprise : la règle des epochs

> **1 epoch = parfait (loss ~0.088)**
> **2 epochs = début d'overfitting**
> **3 epochs = overfitting confirmé (loss chute à ~0.55 = mémorisation)**

Ne jamais dépasser 1 epoch sur ce dataset.

---

## V3 — Problème identifié ❌

Le modèle de base **Mistral v0.3** ne respecte pas bien le `role: system`. Il le colle dans le premier `[INST]` sans séparation claire — le system prompt est donc affaibli à l'inférence, d'où les hallucinations et réponses incohérentes malgré un bon fine-tuning.

---

## V3 — Leçon critique : gestion du stockage RunPod

### Anatomie du stockage RunPod

| Partition | Chemin | Taille typique | Persistance |
|---|---|---|---|
| Container Disk (overlay `/`) | `/tmp/` | 20-30 Go | ❌ Perdu au terminate |
| Network Volume | `/workspace/` | 20-50 Go | ✅ Survit au terminate |

### Le problème de l'export GGUF

`save_pretrained_gguf` crée **3 couches de fichiers** en même temps :

```
GGUF_DIR/                     ← safetensors mergés   (~14 Go)
GGUF_DIR_gguf/
  ├── model.BF16.gguf          ← conversion intermédiaire (~14 Go, supprimée après)
  └── model.Q4_K_M.gguf        ← fichier final         (~4 Go)
```

**Total au pic : ~32 Go simultanément.**

### Solutions testées

| Approche | Résultat |
|---|---|
| Tout sur `/tmp/` (30 Go) | ❌ Sature, Q4_K_M corrompu (1.9 Go au lieu de 4.1 Go) |
| Tout sur `/workspace/` (20 Go libre) | ❌ Pas assez de place non plus |
| **Symlink : safetensors → `/tmp/`, GGUF → `/workspace/`** | ✅ Fonctionne |

### La solution symlink (V3)

Unsloth crée toujours le dossier des GGUF à `GGUF_DIR + "_gguf"`. On exploite ça :

```python
GGUF_DIR      = "/tmp/arnaud-clone-gguf"          # safetensors (~14 Go) → container disk
GGUF_DIR_GGUF = "/workspace/work/arnaud-clone-gguf_gguf"  # GGUF (~18 Go) → volume persistant

os.makedirs(GGUF_DIR, exist_ok=True)
os.makedirs(GGUF_DIR_GGUF, exist_ok=True)

# Symlink AVANT que unsloth crée le dossier _gguf
symlink_path = GGUF_DIR + "_gguf"
if not os.path.exists(symlink_path):
    os.symlink(GGUF_DIR_GGUF, symlink_path)
```

**Répartition finale :**
- `/tmp/` : 14 Go (safetensors) → container disk ✅
- `/workspace/` : 18 Go (BF16 intermédiaire + Q4_K_M final) → volume persistant ✅

---

## V4 — Plan

### Objectif

Corriger la cohérence conversationnelle : le clone doit **comprendre qui il est** et **répondre de manière cohérente** à ce qu'on lui dit.

### Changements prévus

| Paramètre | V3 | V4 | Pourquoi |
|---|---|---|---|
| Modèle de base | `mistral-7b-instruct-v0.3` | `Llama-3.2-3B-Instruct` ou `Phi-3.5-mini-instruct` | Meilleur support natif du system prompt |
| `LORA_RANK` | 32 | 64 | Plus de capacité pour ancrer l'identité |
| Epochs | 1 | 1 | Règle absolue, ne pas toucher |
| Dataset | 8 734 exemples | Idem ou filtrage renforcé | Pas le problème principal |

### Pourquoi changer de modèle de base ?

- **Llama 3.2** et **Phi-3.5** ont un format `<|system|>` dédié dans leur template — le system prompt est vraiment isolé et respecté à l'inférence.
- **Mistral** n'a pas de token system natif → le system prompt se noie dans le contexte conversationnel.

### Script train.py V4

Seuls les changements par rapport à V3 :

```python
# V4 — Changer ces 2 lignes dans train.py

MODEL_NAME = "unsloth/Phi-3.5-mini-instruct"   # ou "unsloth/Llama-3.2-3B-Instruct"
LORA_RANK  = 64                                  # était 32 en V3
LORA_ALPHA = 64                                  # toujours égal à LORA_RANK

# ET changer le chat_template ligne 72 :
tokenizer = get_chat_template(
    tokenizer,
    chat_template = "phi-3",    # ou "llama-3" selon le modèle choisi
)
```

> **Note** : `02_convert_chatml.py` et le dataset ne changent pas — le system prompt est déjà correctement injecté dans chaque exemple.

### Script export.py V4

Identique à V3 — la solution symlink reste valable :

```python
os.environ["HF_HOME"] = "/workspace/work/hf-cache"

CHECKPOINT    = "/workspace/work/arnaud-clone-lora"
GGUF_DIR      = "/tmp/arnaud-clone-gguf"
GGUF_DIR_GGUF = "/workspace/work/arnaud-clone-gguf_gguf"

os.makedirs(GGUF_DIR, exist_ok=True)
os.makedirs(GGUF_DIR_GGUF, exist_ok=True)
symlink_path = GGUF_DIR + "_gguf"
if not os.path.exists(symlink_path):
    os.symlink(GGUF_DIR_GGUF, symlink_path)

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = CHECKPOINT,
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit = True,
)

model.save_pretrained_gguf(
    GGUF_DIR,
    tokenizer,
    quantization_method = "q4_k_m",
)
```

### Checklist RunPod V4

```
[ ] 1. Lancer un pod avec GPU A40 ou mieux (≥ 44 Go VRAM)
[ ] 2. Vérifier l'espace : df -h /workspace /tmp /
[ ] 3. Uploader train.py, export.py, train.jsonl, val.jsonl
[ ] 4. Lancer : python train.py
[ ] 5. Vérifier loss finale ~0.08-0.09 (pas en dessous de 0.07 = overfitting)
[ ] 6. Nettoyer avant export : rm -rf /tmp/arnaud-clone-gguf* /workspace/work/arnaud-clone-gguf*
[ ] 7. Lancer : python export.py
[ ] 8. Vérifier taille GGUF : ls -lh /workspace/work/arnaud-clone-gguf_gguf/
[ ] 9. Télécharger le .gguf + Modelfile
[ ] 10. ollama create arnaud-sage-v4 -f Modelfile && ollama run arnaud-sage-v4
```

---

## Fichiers locaux importants

| Fichier | Description |
|---|---|
| `data/LLM_DATA/mistral-7b-instruct-v0.3.Q4_K_M.gguf` | Modèle V3 (4.1 Go) |
| `data/LLM_DATA/Modelfile` | Config Ollama V3 (avec system prompt + paramètres) |
| `data/LLM_DATA/SYS_PROMPT_ARNAUD` | System prompt source |
| `src/scripts/04_clone/03_finetune_runpod/train.py` | Script fine-tuning |
| `src/scripts/04_clone/03_finetune_runpod/export.py` | Script export GGUF (solution symlink) |
| `src/scripts/04_clone/02_convert_chatml.py` | Génération du dataset ChatML |
