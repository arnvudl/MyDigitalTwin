# AXE 1 — Clone Conversationnel (Fine-tuning)
_Mise à jour : 2026-04-10 — Passage de RAG à Fine-tuning externe_

---

## Nouvelle Stratégie : Fine-tuning Cloud (RunPod / Vast.ai)

Plutôt que d'utiliser un RAG (Retrieval-Augmented Generation) qui injecte des exemples dans le contexte, nous allons **fine-tuner** un modèle (type Llama 3 ou Mistral) pour qu'il adopte nativement le style d'Arnaud.

### Pourquoi ce changement ?
- **Qualité** : Le modèle "devient" Arnaud au lieu de l'imiter via des exemples.
- **Inférence** : Pas besoin de base vectorielle ou de recherche de contexte à chaque message.
- **Coût** : Utilisation ponctuelle de GPU puissants (A100/H100) pour l'entraînement, puis export du modèle quantifié pour usage local ou léger.

---

## Pré-traitement Manuel "Hyper-Quali" (Action Arnaud)

Pour minimiser le temps de GPU payant et maximiser la qualité, un nettoyage drastique et manuel est nécessaire. **L'objectif est d'avoir 500 à 1000 paires (Instruction, Réponse) parfaites.**

### 1. Sélection des conversations (DMs Instagram / WhatsApp / TikTok)
- **Filtrage** : Garder uniquement les échanges où Arnaud est "lui-même" (humour, sarcasme, passion).
- **Anonymisation** : Remplacer les noms des amis par "Ami 1", "Ami 2", etc.
- **Élagage** : Supprimer les messages inutiles ("Ok", "Ça marche", "T'es où ?").
- **Contexte** : Si une réponse d'Arnaud dépend d'une image ou d'un lien, ajouter une description textuelle entre crochets `[Photo d'un setup PC]`.

### 2. Formatage du Dataset (JSONL)
Le fichier final doit ressembler à ceci (format Llama 3 / Alpaca) :
```json
{"instruction": "Message de l'ami", "context": "Contexte optionnel de la conv", "response": "Réponse d'Arnaud"}
```
Ou format Chat :
```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

### 3. "Data Augmentation" Manuelle
- Réécrire certains messages trop courts pour qu'ils soient plus représentatifs du style global.
- Créer des paires "Question/Réponse" sur des sujets précis (Data Science, Musique, Projets) pour ancrer les connaissances.

---

## Workflow Technique

1. **Local** : Préparation du dataset `dataset_arnaud_final.jsonl`.
2. **Cloud (RunPod/Vast.ai)** :
   - Location d'une instance avec **24Go+ VRAM** (RTX 3090/4090 ou A10G).
   - Utilisation de **Axolotl** ou **Unsloth** pour un fine-tuning rapide et optimisé (QLoRA).
   - Entraînement (environ 1-2h pour un petit dataset de haute qualité).
3. **Export** : 
   - Sauvegarde des adaptateurs LoRA sur Hugging Face ou Google Drive.
   - Fusion (merge) avec le modèle de base.
   - Quantification en GGUF (via llama.cpp) pour faire tourner le clone sur le PC local (CPU/GPU 8Go).

---

## Coûts Estimés
- **Location GPU** : ~0.40$ - 0.80$ / heure.
- **Temps total** : 3-5h (setup + train + export) = **< 5$**.

---

## Dashboard — Intégration
La page `/clone` utilisera soit :
- Une API locale (Ollama avec le modèle GGUF personnalisé).
- Un endpoint d'inférence léger si déployé.
