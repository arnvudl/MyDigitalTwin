"""
Fine-tuning Mistral 7B Instruct avec Unsloth (QLoRA 4-bit).
Version 2.3 — Spéciale RunPod (Dataset Robuste)
"""

from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq
from unsloth import is_bfloat16_supported
import torch
import os

# ─── CONFIG ────────────────────────────────────────────────────────────────────

# Utilise la v0.3 qui a réussi à charger tout à l'heure
MODEL_NAME   = "unsloth/mistral-7b-instruct-v0.3-bnb-4bit"
OUTPUT_DIR   = "/workspace/work/arnaud-clone-lora"
GGUF_DIR     = "/workspace/work/arnaud-clone-gguf"

# Chemins dataset sur le Pod
TRAIN_FILE   = "/workspace/work/train.jsonl"
VAL_FILE     = "/workspace/work/val.jsonl"

MAX_SEQ_LEN  = 2048    
LOAD_IN_4BIT = True    

# ─── HYPERPARAMÈTRES QLoRA ─────────────────────────────────────────────────────

LORA_RANK      = 32    
LORA_ALPHA     = 32    
LORA_DROPOUT   = 0     

BATCH_SIZE          = 2    
GRAD_ACCUMULATION   = 4    
LEARNING_RATE       = 2e-4
NUM_EPOCHS          = 3    
WARMUP_RATIO        = 0.05
LR_SCHEDULER        = "cosine"
WEIGHT_DECAY        = 0.01

# ─── CHARGEMENT MODÈLE ─────────────────────────────────────────────────────────

print(f"Chargement du modèle {MODEL_NAME}...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name     = MODEL_NAME,
    max_seq_length = MAX_SEQ_LEN,
    dtype          = None,           
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
    use_gradient_checkpointing = "unsloth",
    random_state   = 42,
)

# ─── TOKENIZER + TEMPLATE ──────────────────────────────────────────────────────

tokenizer = get_chat_template(
    tokenizer,
    chat_template = "mistral",
)

def format_conversations(examples):
    """Transforme le format JSONL en texte prêt pour l'entraînement."""
    convos = examples["conversations"]
    system = examples["system"]
    full_convos = []
    
    for sys, conv in zip(system, convos):
        # On injecte le system prompt
        full = [{"role": "system", "content": sys}]
        
        for msg in conv:
            # On détecte le format des clés (robuste)
            role_key = "role" if "role" in msg else "from"
            content_key = "content" if "content" in msg else "value"
            
            role = msg[role_key]
            # Normalisation des rôles
            if role in ["human", "user"]: role = "user"
            if role in ["gpt", "assistant"]: role = "assistant"
            
            full.append({"role": role, "content": msg[content_key]})
            
        # Application du template Mistral (<s>[INST]...[/INST]...)
        full_convos.append(tokenizer.apply_chat_template(
            full,
            tokenize = False,
            add_generation_prompt = False,
        ))
    return {"text": full_convos}

# ─── DATASET ───────────────────────────────────────────────────────────────────

print("Chargement des datasets...")
dataset = load_dataset(
    "json",
    data_files = {"train": TRAIN_FILE, "validation": VAL_FILE},
)

# Application du formattage (On ne fait PAS de standardize_sharegpt ici)
dataset["train"]      = dataset["train"].map(format_conversations, batched=True)
dataset["validation"] = dataset["validation"].map(format_conversations, batched=True)

print(f"Train      : {len(dataset['train'])} exemples")
print(f"Validation : {len(dataset['validation'])} exemples")

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
        logging_steps    = 10,
        eval_steps       = 100,
        save_steps       = 100,
        save_total_limit = 2,
        output_dir       = OUTPUT_DIR,
        optim            = "adamw_8bit",
        seed             = 42,
        report_to        = "none",
    ),
)

print("\nDémarrage du fine-tuning...")
trainer.train()

# ─── SAUVEGARDE LORA ───────────────────────────────────────────────────────────

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"\nPoids LoRA sauvegardés : {OUTPUT_DIR}")

# ─── EXPORT GGUF (pour Ollama) ─────────────────────────────────────────────────

print("\nExport GGUF Q4_K_M pour Ollama...")
# Création du dossier si besoin
os.makedirs(GGUF_DIR, exist_ok=True)

model.save_pretrained_gguf(
    GGUF_DIR,
    tokenizer,
    quantization_method = "q4_k_m",
)
print(f"GGUF sauvegardé dans : {GGUF_DIR}")
print("\nFélicitations Arnaud, ton clone est prêt !")
