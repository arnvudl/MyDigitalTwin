# Fine-tuning Arnaud Clone — Guide RunPod

## Configuration utilisée

| Parametre | Valeur |
|---|---|
| GPU | A40 (48 Go VRAM) Spot $0.22/hr |
| Template | Unsloth (tout preinstalle) |
| GPU Count | 1 |
| Container Disk | 20 Go |
| Volume Disk | 20 Go (persiste si tu stops le pod) |
| Cout estime | ~$0.50 total (~2h) |

---

## Etapes

### 1. Lancer le pod

1. [runpod.io](https://runpod.io) -> "Deploy" -> "GPU Pods"
2. Selectionne **A40 Spot** ($0.22/hr)
3. Template : **Unsloth**
4. GPU Count : 1 | Container Disk : 20 Go | Volume Disk : 20 Go
5. Lance -> "Connect" -> "Start Web Terminal"

### 2. Uploader les fichiers

Dans le terminal RunPod :

```bash
# Depuis ton terminal local (remplace <POD_IP> et <PORT>)
scp -P <PORT> data/LLM_DATA/train.jsonl root@<POD_IP>:/workspace/
scp -P <PORT> data/LLM_DATA/val.jsonl   root@<POD_IP>:/workspace/
scp -P <PORT> src/scripts/04_clone/03_finetune_runpod/train.py root@<POD_IP>:/workspace/
```

Ou utilise le bouton "Upload" dans l'interface web RunPod (plus simple).

### 3. Tester avant de lancer (optionnel mais recommande)

```bash
# Ajoute max_steps=10 dans TrainingArguments de train.py pour un test rapide
python train.py
```

Si pas d'erreur en 10 steps -> supprime `max_steps`, relance pour le vrai.

### 4. Lancer le fine-tuning

```bash
cd /workspace
python train.py
```

Duree : ~2h sur A40. Logs toutes les 25 steps.  
Tu peux stopper le pod et revenir — les checkpoints sont sauvegardes sur le Volume Disk.

### 5. Telecharger le modele

A la fin, `arnaud-clone-gguf/` contient le `.gguf` pour Ollama.

```bash
# Depuis ton terminal local
scp -P <PORT> -r root@<POD_IP>:/workspace/arnaud-clone-gguf ./
```

Ou zip + telecharge depuis l'interface web RunPod.

---

## Fichiers generes

```
/workspace/
  arnaud-clone-lora/       <- poids LoRA (~200 Mo)
  arnaud-clone-gguf/       <- modele pour Ollama (~4 Go)
    unsloth.Q4_K_M.gguf
```

---

## Apres le telechargement

Voir `04_deploy_local/` pour brancher le modele sur Ollama et le dashboard.
