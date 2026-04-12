"""
Extraction du corpus de fine-tuning pour le clone conversationnel.

Stratégie :
- Sliding window sur chaque conversation individuelle
- Sampling temporel stratifié (couvre début + milieu + fin)
- Scoring par fenêtre (qualité > quantité)
- Cap par personne pour équilibrer le dataset
- Export JSONL au format ChatML (compatible Mistral fine-tuning)
"""

import json
import glob
import os
import re
import random
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────

BASE_DIR = Path("C:/Users/arnau/Documents/MyDigitalTwin")
INBOX = BASE_DIR / "data/raw/INSTAGRAM/your_instagram_activity/messages/inbox"
OUTPUT = BASE_DIR / "data/LLM_DATA/dataset_auto.jsonl"

ARNAUD = "A R N A U D"

# Personnes sélectionnées → dossiers Instagram correspondants
CONVERSATIONS = {
    "djyoyo":    ["djyoyo_489918669070722"],
    "evan":      ["evan_17940018788164627"],
    "lou":       ["lou_1085673686153338"],
    "maelle":    ["maelle_17935615418472883"],
    "nana":      ["nana_18068525429472883"],
    "pilou":     ["pilou_519116326140721"],
    "laura":     ["laura_994708765285921"],
    "jen":       ["jen_945836883473151"],
    "alice":     ["alice_1204248657633025"],
    "loulou":    ["loulou_1188711339191134"],
    "laure":     ["laure_1094343585289278"],
    "fafie":     ["fafie_1121444139243508"],
    "gabi":      ["gabi_1275393733851743"],
    "manonvandy":["manonvandy_1292074112190912"],
    "mylene":    ["mylene_802792480745084"],
    "ama":       ["ama_17970077582700199"],
    "eliott":    ["3li0tttt_17939266904472883"],
    "paulina":   ["_paulinalambin_824971795573896"],
    "celia":     ["celia_1366428128080987"],
    "vic":       ["vic_1114899529906843"],
    "romane":    ["romane_1357028805748638"],
}

WINDOW_SIZE  = 70   # Taille de la fenêtre glissante (messages)
WINDOW_STEP  = 35   # Pas — réduit l'overlap à ~50% (était 71% avec step=20)
N_STRATA     = 5    # Tranches temporelles par conv (couverture début→fin)
MIN_SCORE    = 10   # Seuil minimum — en dessous le window est trop pauvre

# Messages à ignorer (bruit Instagram)
NOISE_PATTERNS = [
    r"^Vous avez envoyé une pièce jointe",
    r"^Vous avez répondu à votre story",
    r"^Vous avez réagi",
    r"^Reacted .* to your message",
    r"^Liked a message",
    r"^(Appel|Appel vidéo) (manqué|terminé)",
    r"^You set the nickname",
    r"^\S+ set your nickname",
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

# Marqueurs haute fréquence (vraiment distinctifs, pas du français générique)
# Source : analyse statistique sur 62k messages Arnaud (Lou+Nana+Maelle+Alice)
SLANG_HF_RE = re.compile(
    r"\b(dcp|jsp|genre|fin\b|mtn|att\b|bah|nan\b|wsh|wesh|ptn|tqt|oe\b|cv\b|enft|vrais)\b",
    re.IGNORECASE
)

# Signatures quasi-uniques d'Arnaud (très rares en français général)
SIGNATURE_RE = re.compile(
    r"\b(gnon|mouais|unhun|\bui\b|réel\b|miskine|aïe)\b"
    r"|(mais wsh|oh la+la+|pas compris|alors là|c quoi|nan mais|en vrais?|bah oui|bah non|bah nan)",
    re.IGNORECASE
)

# Raisonnement / analyse (Arnaud philosophe/psy)
REASONING_RE = re.compile(
    r"\b(en gros|je comprends|du coup|parce que|je pense que|c'est logique|c'est normal|"
    r"faut\b|je sais pas mais|en fait|au final|finalement|sauf que|même si)\b",
    re.IGNORECASE
)

# Questions (curiosité naturelle d'Arnaud)
QUESTION_RE = re.compile(r"\?")


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def fix_encoding(text: str) -> str:
    """Instagram exporte en UTF-8 réencodé latin1 — on corrige."""
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def load_conversation(folders: list[str]) -> list[dict]:
    """Charge et fusionne tous les fichiers message_N.json d'une conversation."""
    all_messages = []
    for folder in folders:
        path = INBOX / folder
        files = sorted(glob.glob(str(path / "message_*.json")))
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            all_messages.extend(data["messages"])

    # Instagram → ordre anti-chronologique, on remet dans l'ordre
    all_messages.sort(key=lambda m: m["timestamp_ms"])
    return all_messages


def is_valid_message(msg: dict) -> bool:
    """True si le message contient du texte exploitable."""
    content = msg.get("content", "")
    if not content:
        return False
    if NOISE_RE.search(content):
        return False
    return True


def clean_message(msg: dict) -> dict:
    """Retourne un message nettoyé avec encoding corrigé."""
    return {
        "sender": msg["sender_name"],
        "content": fix_encoding(msg.get("content", "")),
        "timestamp_ms": msg["timestamp_ms"],
    }


def build_windows(messages: list[dict]) -> list[list[dict]]:
    """Extrait toutes les fenêtres glissantes de messages valides."""
    valid = [clean_message(m) for m in messages if is_valid_message(m)]
    windows = []
    for i in range(0, len(valid) - WINDOW_SIZE + 1, WINDOW_STEP):
        windows.append(valid[i : i + WINDOW_SIZE])
    return windows


def score_window(window: list[dict]) -> int:
    """Score une fenêtre selon son intérêt pour le fine-tuning.

    Calibré sur analyse statistique de 62k messages réels d'Arnaud
    (Lou + Nana + Maelle + Alice).

    Critères :
    - Flow multi-messages (son rythme naturel)
    - Marqueurs haute fréquence (dcp, jsp, genre, bah, fin, att…)
    - Signatures uniques (gnon, mouais, unhun, réel, oh lalalala…)
    - Raisonnement / analyse (philosophe + psy)
    - Curiosité (questions)
    - Alternance court/long (son rythme : réactions courtes + explications)
    """
    score = 0
    arnaud_msgs = [m for m in window if m["sender"] == ARNAUD]

    if not arnaud_msgs:
        return -1

    arnaud_text = " ".join(m["content"] for m in arnaud_msgs)
    word_counts = [len(m["content"].split()) for m in arnaud_msgs]

    # ── Flow naturel : plusieurs messages d'affilée ──────────────────
    if len(arnaud_msgs) >= 3:
        score += 2
    if len(arnaud_msgs) >= 6:
        score += 2

    # ── Marqueurs haute fréquence (distinctifs mais courants chez lui) ─
    hf_hits = len(SLANG_HF_RE.findall(arnaud_text))
    if hf_hits >= 2:
        score += 2
    if hf_hits >= 5:
        score += 2

    # ── Signatures quasi-uniques (gnon, mouais, réel, oh lalalala…) ──
    sig_hits = len(SIGNATURE_RE.findall(arnaud_text))
    if sig_hits >= 1:
        score += 3   # très fort signal
    if sig_hits >= 2:
        score += 2

    # ── Raisonnement / mode psy (en gros, du coup, parce que…) ───────
    reasoning_hits = len(REASONING_RE.findall(arnaud_text))
    if reasoning_hits >= 1:
        score += 2
    if reasoning_hits >= 3:
        score += 1

    # ── Curiosité : questions d'Arnaud ───────────────────────────────
    arnaud_questions = sum(1 for m in arnaud_msgs if QUESTION_RE.search(m["content"]))
    if arnaud_questions >= 2:
        score += 2
    if arnaud_questions >= 4:
        score += 1

    # ── Rythme court/long : mix de réactions courtes + messages longs ─
    has_short = any(w <= 3 for w in word_counts)
    has_long  = any(w >= 10 for w in word_counts)
    if has_short and has_long:
        score += 2   # signature rythmique d'Arnaud

    # ── Échange réel (les deux côtés parlent) ────────────────────────
    if any(m["sender"] != ARNAUD for m in window):
        score += 1

    return score


def stratified_sample(windows: list[list[dict]], person: str) -> list[list[dict]]:
    """
    Découpe les fenêtres en N tranches temporelles pour garantir
    la couverture début→fin. Dans chaque tranche, garde TOUT
    ce qui dépasse MIN_SCORE — pas de cap arbitraire.
    """
    if not windows:
        return []

    stratum_size = max(1, len(windows) // N_STRATA)
    selected = []

    for i in range(N_STRATA):
        start = i * stratum_size
        end = start + stratum_size if i < N_STRATA - 1 else len(windows)
        stratum = windows[start:end]

        scored = [(score_window(w), w) for w in stratum]
        # Garde tout ce qui dépasse le seuil minimum
        selected.extend(w for s, w in scored if s >= MIN_SCORE)

    return selected


def window_to_jsonl(window: list[dict]) -> dict:
    """Convertit une fenêtre en entrée JSONL format ChatML."""
    messages = []
    for msg in window:
        role = "assistant" if msg["sender"] == ARNAUD else "user"
        messages.append({"role": role, "content": msg["content"]})
    return {"messages": messages}


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    all_entries = []
    stats = {}

    for person, folders in CONVERSATIONS.items():
        print(f"\n[{person}] Chargement...")

        # Vérifie que les dossiers existent
        missing = [f for f in folders if not (INBOX / f).exists()]
        if missing:
            print(f"  ⚠ Dossiers introuvables : {missing}")
            folders = [f for f in folders if (INBOX / f).exists()]
        if not folders:
            continue

        messages = load_conversation(folders)
        print(f"  {len(messages)} messages chargés")

        windows = build_windows(messages)
        print(f"  {len(windows)} fenêtres extraites")

        selected = stratified_sample(windows, person)
        print(f"  {len(selected)} fenêtres retenues (sampling stratifié)")

        entries = [window_to_jsonl(w) for w in selected]
        all_entries.extend(entries)
        stats[person] = len(entries)

    # Mélange pour éviter que toutes les convos d'une même personne soient groupées
    random.shuffle(all_entries)

    # Export
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Résumé
    print("\n" + "=" * 50)
    print(f"Dataset exporté : {OUTPUT}")
    print(f"Total : {len(all_entries)} exemples\n")
    print("Répartition par personne :")
    for person, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {person:15s} {count:4d} exemples")


if __name__ == "__main__":
    main()
