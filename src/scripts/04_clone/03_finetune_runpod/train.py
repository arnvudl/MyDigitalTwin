"""
Fine-tuning Mistral 7B Instruct avec Unsloth (QLoRA 4-bit).
A exécuter sur RunPod — ne pas lancer en local (8Go VRAM insuffisant).

Prérequis RunPod :
  - Template : "Unsloth" ou "PyTorch 2.x + CUDA 12.x"
  - GPU : RTX 3090 (24Go) ou RTX 4090 recommandé
  - Disk : 30 Go minimum

Installation (première fois seulement) :
  pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
  pip install --no-deps trl peft accelerate bitsandbytes
"""

from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template, standardize_sharegpt
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq
from unsloth import is_bfloat16_supported
import torch

# ─── CONFIG ────────────────────────────────────────────────────────────────────

MODEL_NAME   = "mistralai/Mistral-7B-Instruct-v0.3"
OUTPUT_DIR   = "/workspace/work/arnaud-clone-lora"   # poids LoRA (persistant)
MERGED_DIR   = "/workspace/work/arnaud-clone-merged"  # modèle fusionné
GGUF_DIR     = "/workspace/work/arnaud-clone-gguf"    # export Ollama (persistant)

# Chemins dataset — uploader dans /workspace/work/
TRAIN_FILE   = "/workspace/work/train.jsonl"
VAL_FILE     = "/workspace/work/val.jsonl"

MAX_SEQ_LEN  = 2048    # 70 messages ~ 600 tokens, 2048 est largement suffisant
LOAD_IN_4BIT = True    # QLoRA 4-bit

# ─── HYPERPARAMÈTRES QLoRA ─────────────────────────────────────────────────────
# Calibrés pour Mistral 7B sur 6k exemples conversationnels

LORA_RANK      = 32    # Plus élevé = plus de capacité, plus de VRAM (16 ou 32)
LORA_ALPHA     = 32    # Même valeur que rank = bonne pratique
LORA_DROPOUT   = 0     # 0 recommandé par Unsloth

BATCH_SIZE          = 2    # Par GPU — augmenter si VRAM > 24Go
GRAD_ACCUMULATION   = 4    # Batch effectif = 2 × 4 = 8
LEARNING_RATE       = 2e-4
NUM_EPOCHS          = 3    # 3 epochs sur 6k exemples = bon équilibre
WARMUP_RATIO        = 0.05
LR_SCHEDULER        = "cosine"
WEIGHT_DECAY        = 0.01

# ─── CHARGEMENT MODÈLE ─────────────────────────────────────────────────────────

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name     = MODEL_NAME,
    max_seq_length = MAX_SEQ_LEN,
    dtype          = None,           # auto-détection (bfloat16 sur Ampere+)
    load_in_4bit   = LOAD_IN_4BIT,
)

# ─── ADAPTATEURS LoRA ──────────────────────────────────────────────────────────

model = FastLanguageModel.get_peft_model(
    model,
    r              = LORA_RANK,
    target_modules = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha     = LORA_ALPHA,
    lora_dropout   = LORA_DROPOUT,
    bias           = "none",
    use_gradient_checkpointing = "unsloth",  # économise VRAM
    random_state   = 42,
)

# ─── TOKENIZER + TEMPLATE ──────────────────────────────────────────────────────

tokenizer = get_chat_template(
    tokenizer,
    chat_template = "mistral",
)

def format_conversations(examples):
    convos = examples["conversations"]
    # Injecte le system prompt dans chaque conversation
    system  = examples["system"]
    full_convos = []
    for sys, conv in zip(system, convos):
        full = [{"role": "system", "content": sys}]
        for msg in conv:
            role = "user" if msg["from"] == "human" else "assistant"
            full.append({"role": role, "content": msg["value"]})
        full_convos.append(tokenizer.apply_chat_template(
            full,
            tokenize      = False,
            add_generation_prompt = False,
        ))
    return {"text": full_convos}

# ─── DATASET ───────────────────────────────────────────────────────────────────

dataset = load_dataset(
    "json",
    data_files = {"train": TRAIN_FILE, "validation": VAL_FILE},
)

dataset["train"]      = standardize_sharegpt(dataset["train"])
dataset["validation"] = standardize_sharegpt(dataset["validation"])

dataset["train"]      = dataset["train"].map(format_conversations, batched=True)
dataset["validation"] = dataset["validation"].map(format_conversations, batched=True)

print(f"Train      : {len(dataset['train'])} exemples")
print(f"Validation : {len(dataset['validation'])} exemples")
print("\nExemple formaté :")
print(dataset["train"][0]["text"][:500])

# ─── ENTRAÎNEMENT ──────────────────────────────────────────────────────────────

trainer = SFTTrainer(
    model     = model,
    tokenizer = tokenizer,
    train_dataset = dataset["train"],
    eval_dataset  = dataset["validation"],
    dataset_text_field = "text",
    max_seq_length     = MAX_SEQ_LEN,
    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer),
    dataset_num_proc = 2,
    packing  = False,
    args = TrainingArguments(
        per_device_train_batch_size      = BATCH_SIZE,
        gradient_accumulation_steps      = GRAD_ACCUMULATION,
        num_train_epochs                 = NUM_EPOCHS,
        warmup_ratio                     = WARMUP_RATIO,
        learning_rate                    = LEARNING_RATE,
        weight_decay                     = WEIGHT_DECAY,
        lr_scheduler_type                = LR_SCHEDULER,
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps    = 25,
        eval_steps       = 200,
        save_steps       = 200,
        save_total_limit = 3,
        output_dir       = OUTPUT_DIR,
        optim            = "adamw_8bit",
        seed             = 42,
        report_to        = "none",     # pas de wandb
    ),
)

print("\nDemarrage du fine-tuning...")
trainer.train()

# ─── SAUVEGARDE LORA ───────────────────────────────────────────────────────────

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"\nPoids LoRA sauvegardes : {OUTPUT_DIR}")

# ─── EXPORT GGUF (pour Ollama en local) ────────────────────────────────────────

print("\nExport GGUF Q4_K_M pour Ollama...")
model.save_pretrained_gguf(
    GGUF_DIR,
    tokenizer,
    quantization_method = "q4_k_m",   # meilleur ratio qualite/taille pour 8Go VRAM
)
print(f"GGUF sauvegarde : {GGUF_DIR}")
print("\nFin ! Telecharge le dossier arnaud-clone-gguf/ pour Ollama.")
