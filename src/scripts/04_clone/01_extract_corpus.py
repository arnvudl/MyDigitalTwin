"""
Extraction du corpus de fine-tuning pour le clone conversationnel (v2.2).

Améliorations v2.2 :
- Suppression du filtre "type" (absent des JSON Instagram).
- Fix de l'encodage Latin-1 -> UTF-8.
- Filtrage du bruit Instagram (appels, partages, métadonnées).
- Chaque exemple se termine impérativement par un bloc d'Arnaud.
"""

import json
import glob
import os
import re
import random
import sys
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from config import LLM_DATA, INSTAGRAM_INBOX, INSTAGRAM_SENDER_NAME, CLONE_CONVERSATIONS

INBOX  = Path(INSTAGRAM_INBOX)
OUTPUT = Path(LLM_DATA) / "dataset_final.jsonl"

ARNAUD        = INSTAGRAM_SENDER_NAME
CONVERSATIONS = CLONE_CONVERSATIONS

# Paramètres v2
CONTEXT_SIZES = [2, 5, 12, 25, 40]  # Nombre de blocs (tours de parole) en arrière
MIN_SCORE     = 7                   # Score min pour retenir une fenêtre (baissé à 7)

# Bruit à filtrer (après décodage UTF-8 propre)
NOISE_PATTERNS = [
    r"envoyé une pièce jointe",
    r"répondu à votre story",
    r"réagi à votre message",
    r"reacted .* to your message",
    r"liked a message",
    r"started an audio call",
    r"audio call ended",
    r"missed an audio call",
    r"appel (manqué|terminé|vidéo)",
    r"set the nickname",
    r"set your nickname",
    r"0 replies 0 retweets 0 likes",
    r"view post on instagram",
    r"a partagé une publication",
    r"partagé un profil",
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

# Lexique Arnaud (Scoring)
SLANG_HF_RE = re.compile(r"\b(dcp|jsp|genre|fin\b|mtn|att\b|bah|nan\b|wsh|wesh|ptn|tqt|oe\b|cv\b|enft|vrais)\b", re.IGNORECASE)
SIGNATURE_RE = re.compile(r"\b(gnon|mouais|unhun|\bui\b|réel\b|miskine|aïe)\b|(mais wsh|oh la+la+|pas compris|alors là|c quoi|nan mais|en vrais?|bah oui|bah non|bah nan)", re.IGNORECASE)
REASONING_RE = re.compile(r"\b(en gros|je comprends|du coup|parce que|je pense que|c'est logique|c'est normal|faut\b|je sais pas mais|en fait|au final|finalement|sauf que|même si)\b", re.IGNORECASE)

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def fix_encoding(text: str) -> str:
    """Instagram encode les caractères non-ASCII en s'appuyant sur latin-1."""
    if not text: return ""
    try:
        # On encode en latin-1 pour récupérer les bytes bruts, puis on décode en utf-8
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def load_conversation(folders: list[str]) -> list[dict]:
    all_messages = []
    for folder in folders:
        path = INBOX / folder
        files = glob.glob(str(path / "message_*.json"))
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            all_messages.extend(data["messages"])
    all_messages.sort(key=lambda m: m["timestamp_ms"])
    return all_messages

def is_valid_message(msg: dict) -> bool:
    content_raw = msg.get("content", "")
    content = fix_encoding(content_raw)
    
    # Exclure si pas de texte (photos, vidéos, cadeaux...)
    if not content:
        return False
    
    # Exclure les partages explicites (métadonnées JSON)
    if any(k in msg for k in ["share", "photos", "videos", "audio_files", "files"]):
        return False
    
    # Exclure les appels
    if "call_duration" in msg:
        return False

    # Exclure via patterns regex
    if NOISE_RE.search(content):
        return False
        
    return True

def group_messages(messages: list[dict]) -> list[dict]:
    """Groupe les messages consécutifs du même expéditeur en un bloc."""
    if not messages: return []
    
    blocks = []
    first_msg = messages[0]
    current_block = {
        "sender": first_msg["sender_name"],
        "content": [fix_encoding(first_msg.get("content", ""))],
        "count": 1
    }
    
    for m in messages[1:]:
        sender = m["sender_name"]
        content = fix_encoding(m.get("content", ""))
        
        if sender == current_block["sender"]:
            current_block["content"].append(content)
            current_block["count"] += 1
        else:
            blocks.append({
                "sender": current_block["sender"],
                "content": "\n".join(current_block["content"]),
                "msg_count": current_block["count"]
            })
            current_block = {"sender": sender, "content": [content], "count": 1}
            
    blocks.append({
        "sender": current_block["sender"],
        "content": "\n".join(current_block["content"]),
        "msg_count": current_block["count"]
    })
    return blocks

def score_block(content: str, is_arnaud: bool) -> int:
    """Score un bloc de messages selon l'intérêt stylistique."""
    if not is_arnaud: return 0
    score = 0
    
    # Signatures et Slang
    score += len(SIGNATURE_RE.findall(content)) * 3
    score += len(SLANG_HF_RE.findall(content)) * 1.5
    score += len(REASONING_RE.findall(content)) * 2
    
    # Monologue (plusieurs messages groupés)
    lines = content.count("\n") + 1
    if lines >= 3: score += 3
    if lines >= 6: score += 4
    
    # Longueur
    words = len(content.split())
    if words > 30: score += 2
    if words > 100: score += 3
    
    return int(score)

# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    all_entries = []
    
    for person, folders in CONVERSATIONS.items():
        print(f"[{person}] Processing...")
        # Filtrage AVANT le groupage
        raw_messages = [m for m in load_conversation(folders) if is_valid_message(m)]
        blocks = group_messages(raw_messages)
        
        person_entries = []
        
        # Pour chaque bloc d'Arnaud, on crée des exemples avec différents contextes
        for i, block in enumerate(blocks):
            if block["sender"] != ARNAUD:
                continue
            
            # Score du bloc cible
            target_score = score_block(block["content"], True)
            
            # On génère des fenêtres de tailles différentes se terminant ici
            for size in CONTEXT_SIZES:
                if i < size: continue
                
                window = blocks[i-size : i+1]
                
                # On s'assure que le dernier bloc est bien Arnaud
                if window[-1]["sender"] != ARNAUD: continue
                
                # Calcul du score global de la fenêtre
                history_text = " ".join(b["content"] for b in window[:-1])
                history_score = len(SLANG_HF_RE.findall(history_text)) + len(REASONING_RE.findall(history_text))
                
                total_score = target_score + (history_score / size)
                
                if total_score >= MIN_SCORE:
                    messages = []
                    for b in window:
                        role = "assistant" if b["sender"] == ARNAUD else "user"
                        messages.append({"role": role, "content": b["content"]})
                    
                    person_entries.append({"messages": messages, "score": total_score})

        # Stratified sampling : on garde les meilleurs de chaque personne
        person_entries.sort(key=lambda x: x["score"], reverse=True)
        # Cap à 800 exemples par personne pour l'équilibre
        all_entries.extend(person_entries[:800])
        print(f"  {len(person_entries[:800])} exemples retenus")

    random.shuffle(all_entries)
    
    if not all_entries:
        print("!!! ERREUR : Aucun exemple n'a été retenu. Vérifie les scores ou le sender name.")
        return

    # Création dossier de sortie si besoin
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for entry in all_entries:
            final_entry = {"messages": entry["messages"]}
            f.write(json.dumps(final_entry, ensure_ascii=False) + "\n")

    print(f"\nTerminé ! {len(all_entries)} exemples dans {OUTPUT}")

if __name__ == "__main__":
    main()
