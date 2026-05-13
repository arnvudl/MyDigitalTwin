import sys
import os

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

import json  # noqa: E402
import re  # noqa: E402
import pandas as pd  # noqa: E402
from config import (  # noqa: E402
    WAREHOUSE,
    INSTAGRAM_INBOX,
    CLOSE_FRIENDS,
    CLOSE_FRIENDS_MULTIPLIER,
    MIN_MESSAGES,
)


def _parse_conversation(conv_dir: str, folder: str) -> dict | None:
    msg_files = sorted(
        [f for f in os.listdir(conv_dir) if f.startswith("message_") and f.endswith(".json")],
        key=lambda f: int(re.search(r"(\d+)", f).group(1)),
        reverse=True,
    )
    if not msg_files:
        return None

    with open(os.path.join(conv_dir, msg_files[0]), encoding="utf-8") as f:
        data = json.load(f)

    if len(data.get("participants", [])) != 2:
        return None

    msg_count = 0
    for fname in msg_files:
        with open(os.path.join(conv_dir, fname), encoding="utf-8") as f:
            msg_count += len(json.load(f).get("messages", []))

    if msg_count < MIN_MESSAGES:
        return None

    label    = re.split(r"_\d{10,}", folder)[0].lower()
    node_id  = folder.lower()
    is_close = (label in CLOSE_FRIENDS) or (node_id in CLOSE_FRIENDS)

    return {
        "node_id":          node_id,
        "label":            label,
        "message_count":    msg_count,
        "in_close_friends": is_close,
    }


def main():
    inbox = INSTAGRAM_INBOX
    os.makedirs(WAREHOUSE, exist_ok=True)

    if not os.path.exists(inbox):
        print(f"  ⚠ Instagram inbox introuvable : {inbox}")
        return

    print(f"Inbox conversations : {len(os.listdir(inbox))}")
    print(f"Close friends configurés : {len(CLOSE_FRIENDS)}")
    print(f"Multiplicateur           : x{CLOSE_FRIENDS_MULTIPLIER}")
    print(f"Seuil minimum messages   : {MIN_MESSAGES}")

    records = []
    for folder in os.listdir(inbox):
        conv_dir = os.path.join(inbox, folder)
        if not os.path.isdir(conv_dir):
            continue
        result = _parse_conversation(conv_dir, folder)
        if result:
            records.append(result)

    df = pd.DataFrame(records)
    df["weight"] = df.apply(
        lambda row: row["message_count"] * CLOSE_FRIENDS_MULTIPLIER
                    if row["in_close_friends"] else float(row["message_count"]),
        axis=1,
    )
    df = df.sort_values("weight", ascending=False).reset_index(drop=True)

    print(f"\nConversations retenues (>= {MIN_MESSAGES} msgs) : {len(df)}")
    print(f"Close friends : {df['in_close_friends'].sum()}")

    out_dir = os.path.join(WAREHOUSE, "social_graph")
    os.makedirs(out_dir, exist_ok=True)
    df.to_parquet(os.path.join(out_dir, "part-0.parquet"), index=False)

    print(f"\nSauvegarde : {out_dir}")
    print(f"  {len(df)} nœuds, {df['message_count'].sum():,} messages total")

    check = pd.read_parquet(out_dir)
    print(f"  Vérification lecture dossier : {len(check)} lignes OK")


if __name__ == "__main__":
    main()
