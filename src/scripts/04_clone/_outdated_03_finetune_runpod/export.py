from unsloth import FastLanguageModel
import os

os.environ["HF_HOME"] = "/workspace/work/hf-cache"

CHECKPOINT = "/workspace/work/arnaud-clone-lora"

# Répartition du stockage :
# - Unsloth écrit les safetensors (~14 Go) dans GGUF_DIR  → /tmp/ (container, ~28 Go libres)
# - Unsloth écrit BF16 + Q4_K_M (~18 Go) dans GGUF_DIR_gguf → /workspace/ via symlink (~20 Go libres)
GGUF_DIR      = "/tmp/arnaud-clone-gguf"
GGUF_DIR_GGUF = "/workspace/work/arnaud-clone-gguf_gguf"  # destination réelle via symlink

# Créer le symlink AVANT que unsloth ne crée le dossier _gguf
os.makedirs(GGUF_DIR, exist_ok=True)
os.makedirs(GGUF_DIR_GGUF, exist_ok=True)
symlink_path = GGUF_DIR + "_gguf"
if not os.path.exists(symlink_path):
    os.symlink(GGUF_DIR_GGUF, symlink_path)
    print(f"Symlink créé : {symlink_path} -> {GGUF_DIR_GGUF}")

print(f"--- Chargement du checkpoint : {CHECKPOINT} ---")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = CHECKPOINT,
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit = True,
)

print("--- Export GGUF Q4_K_M ---")
model.save_pretrained_gguf(
    GGUF_DIR,
    tokenizer,
    quantization_method = "q4_k_m",
)

print(f"--- TERMINE ! Ton modele GGUF est dans : {GGUF_DIR_GGUF}/ ---")
print("Le Q4_K_M est sur /workspace (persistant). Les safetensors /tmp sont éphémères.")