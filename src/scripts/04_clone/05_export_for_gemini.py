"""
Export d'un corpus lisible pour Gemini Gems (clone conversationnel).

Ce script lit dataset_final.jsonl, re-score chaque exemple,
et exporte les N meilleurs en format texte lisible pour Gemini.

Sorties :
  - data/LLM_DATA/gemini_corpus.txt     ← exemples de conversations (source principale)
  - data/LLM_DATA/gemini_system.txt     ← system prompt prêt à coller dans le Gem
"""

import json
import re
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────

BASE_DIR = Path("C:/Users/arnau/Documents/MyDigitalTwin")

INPUT         = BASE_DIR / "data/LLM_DATA/dataset_final.jsonl"
SYS_PROMPT    = BASE_DIR / "data/LLM_DATA/SYS_PROMPT_ARNAUD"
OUTPUT_CORPUS = BASE_DIR / "data/LLM_DATA/gemini_corpus.txt"
OUTPUT_SYSTEM = BASE_DIR / "data/LLM_DATA/gemini_system.txt"

TOP_N = 300   # Nombre d'exemples à garder (Gemini supporte ~500k tokens)

# ─── SCORING (même logique que 01_extract_corpus.py) ──────────────────────────

SLANG_RE     = re.compile(r"\b(dcp|jsp|genre|fin\b|mtn|att\b|bah|nan\b|wsh|wesh|ptn|tqt|oe\b|cv\b|enft|vrais)\b", re.IGNORECASE)
SIGNATURE_RE = re.compile(r"\b(gnon|mouais|unhun|\bui\b|réel\b|miskine|aïe)\b|(mais wsh|oh la+la+|pas compris|alors là|c quoi|nan mais|en vrais?|bah oui|bah non|bah nan)", re.IGNORECASE)
REASONING_RE = re.compile(r"\b(en gros|je comprends|du coup|parce que|je pense que|c'est logique|c'est normal|faut\b|je sais pas mais|en fait|au final|finalement|sauf que|même si)\b", re.IGNORECASE)

def score_entry(entry: dict) -> float:
    """Score un exemple sur la richesse stylistique des réponses d'Arnaud."""
    score = 0.0
    arnaud_msgs = [m["content"] for m in entry["messages"] if m["role"] == "assistant"]
    for content in arnaud_msgs:
        score += len(SIGNATURE_RE.findall(content)) * 3
        score += len(SLANG_RE.findall(content)) * 1.5
        score += len(REASONING_RE.findall(content)) * 2
        lines = content.count("\n") + 1
        if lines >= 3: score += 3
        if lines >= 6: score += 4
        words = len(content.split())
        if words > 30: score += 2
        if words > 100: score += 3
    return score

# ─── FORMATAGE ─────────────────────────────────────────────────────────────────

def format_entry(entry: dict, idx: int) -> str:
    """Convertit un exemple JSONL en bloc texte lisible."""
    lines = [f"--- Exemple {idx} ---"]
    for msg in entry["messages"]:
        speaker = "Arnaud" if msg["role"] == "assistant" else "Interlocuteur"
        # Chaque message envoyé en rafale est séparé par \n dans le content
        for line in msg["content"].split("\n"):
            line = line.strip()
            if line:
                lines.append(f"{speaker}: {line}")
    lines.append("")  # ligne vide entre exemples
    return "\n".join(lines)

# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    # Lecture du dataset
    entries = []
    with open(INPUT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"Dataset chargé : {len(entries)} exemples")

    # Scoring et tri
    scored = [(score_entry(e), e) for e in entries]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:TOP_N]

    print(f"Top {TOP_N} exemples sélectionnés (score min : {top[-1][0]:.1f}, max : {top[0][0]:.1f})")

    # Export corpus
    with open(OUTPUT_CORPUS, "w", encoding="utf-8") as f:
        f.write("=== CORPUS DE CONVERSATIONS — ARNAUD ===\n")
        f.write(f"Ce fichier contient {TOP_N} exemples réels de conversations d'Arnaud,\n")
        f.write("triés par richesse stylistique (slang, signatures, raisonnement).\n")
        f.write("Utilise-le comme source de référence pour imiter son style.\n\n")
        for i, (score, entry) in enumerate(top, 1):
            f.write(format_entry(entry, i))

    print(f"Corpus exporté : {OUTPUT_CORPUS}")

    # Export system prompt
    system_text = SYS_PROMPT.read_text(encoding="utf-8").strip()
    with open(OUTPUT_SYSTEM, "w", encoding="utf-8") as f:
        f.write(system_text)

    print(f"System prompt exporté : {OUTPUT_SYSTEM}")

    # Stats
    corpus_size = OUTPUT_CORPUS.stat().st_size / 1024
    print(f"\nTaille du corpus : {corpus_size:.0f} Ko")
    print("\nProchaine étape :")
    print("  1. Ouvre Gemini > Gems > Nouveau Gem")
    print("  2. Colle le contenu de gemini_system.txt dans le champ 'Instructions'")
    print("  3. Ajoute gemini_corpus.txt en pièce jointe (Knowledge)")
    print("  4. Teste !")

if __name__ == "__main__":
    main()
