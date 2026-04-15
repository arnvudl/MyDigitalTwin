"""
Conversion du dataset final en format ChatML pour fine-tuning Mistral 7B.
Compatible Unsloth / Axolotl / LLaMA-Factory sur RunPod.

Format de sortie : chaque ligne JSONL contient :
  {
    "system": "...",        ← qui est Arnaud
    "conversations": [
      {"from": "human", "value": "..."},
      {"from": "gpt",   "value": "..."},
      ...
    ]
  }
"""

import json
import os
import sys
import pathlib
import random

# ─── CONFIG ────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from config import LLM_DATA

LLM_DATA = pathlib.Path(LLM_DATA)

# ─── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
# Lu depuis data/LLM_DATA/SYS_PROMPT_ARNAUD — modifie ce fichier pour mettre à jour.

SYSTEM_PROMPT = (LLM_DATA / "SYS_PROMPT_ARNAUD").read_text(encoding="utf-8").strip()
INPUT        = LLM_DATA / "dataset_final.jsonl"
OUTPUT       = LLM_DATA / "dataset_chatml.jsonl"

SPLIT_RATIO  = 0.95   # 95% train, 5% validation
OUTPUT_TRAIN = LLM_DATA / "train.jsonl"
OUTPUT_VAL   = LLM_DATA / "val.jsonl"


# ─── CONVERSION ────────────────────────────────────────────────────────────────

def convert_entry(entry: dict) -> dict | None:
    """
    Convertit une entrée JSONL (format messages user/assistant)
    en format ChatML (human/gpt) avec system prompt.
    Filtre les entrées qui ne commencent pas par un message "user"
    ou qui n'ont pas de réponse "assistant".
    """
    messages = entry.get("messages", [])
    if not messages:
        return None

    # Doit contenir au moins un tour complet (human -> gpt)
    has_human    = any(m["role"] == "user"      for m in messages)
    has_arnaud   = any(m["role"] == "assistant" for m in messages)
    if not has_human or not has_arnaud:
        return None

    conversations = []
    for msg in messages:
        if msg["role"] == "user":
            conversations.append({"from": "human", "value": msg["content"]})
        elif msg["role"] == "assistant":
            conversations.append({"from": "gpt", "value": msg["content"]})

    return {
        "system": SYSTEM_PROMPT,
        "conversations": conversations,
    }


def main():
    with open(INPUT, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = f.readlines()

    converted = []
    skipped = 0
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        result = convert_entry(entry)
        if result:
            converted.append(result)
        else:
            skipped += 1

    # Mélange avant split
    random.shuffle(converted)

    split_idx = int(len(converted) * SPLIT_RATIO)
    train = converted[:split_idx]
    val   = converted[split_idx:]

    # Export dataset complet
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for entry in converted:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Export train / val séparés (pour Unsloth/Axolotl)
    with open(OUTPUT_TRAIN, "w", encoding="utf-8") as f:
        for entry in train:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    with open(OUTPUT_VAL, "w", encoding="utf-8") as f:
        for entry in val:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("=" * 50)
    print(f"Total converti   : {len(converted)} exemples")
    print(f"Ignorés          : {skipped}")
    print(f"Train            : {len(train)} exemples -> {OUTPUT_TRAIN.name}")
    print(f"Validation       : {len(val)} exemples  -> {OUTPUT_VAL.name}")
    print(f"\nDataset complet  : {OUTPUT}")
    print("\nSystem prompt :")
    print(SYSTEM_PROMPT[:200] + "...")


if __name__ == "__main__":
    main()
