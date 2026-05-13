import sys
import os

_d = os.path.abspath(__file__)
while not os.path.exists(os.path.join(_d, "config.py")):
    _p = os.path.dirname(_d)
    if _p == _d:
        raise RuntimeError("config.py introuvable")
    _d = _p
sys.path.insert(0, _d)

from config import (  # noqa: E402
    WAREHOUSE,
    INSTAGRAM_INBOX,
    CLOSE_FRIENDS,
    CLOSE_FRIENDS_MULTIPLIER,
    MIN_MESSAGES,
)
import json  # noqa: E402
import glob  # noqa: E402
import pandas as pd  # noqa: E402


def _parse_conversation(convo_dir: str) -> dict | None:
    """Parse a single Instagram DM conversation directory.

    Returns None if it's a group chat or has fewer than MIN_MESSAGES messages.
    """
    json_files = glob.glob(os.path.join(convo_dir, "message_*.json"))
    if not json_files:
        return None

    all_messages = []
    participants = []
    for path in json_files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not participants:
            participants = [p["name"] for p in data.get("participants", [])]
        all_messages.extend(data.get("messages", []))

    # Only 1-on-1 conversations
    if len(participants) != 2:
        return None

    other = [p for p in participants if p != "arnvudl"]
    if not other:
        return None
    contact = other[0]

    msg_count = len(all_messages)
    if msg_count < MIN_MESSAGES:
        return None

    weight = msg_count * CLOSE_FRIENDS_MULTIPLIER if contact in CLOSE_FRIENDS else msg_count

    return {
        "contact": contact,
        "msg_count": msg_count,
        "weight": weight,
        "is_close_friend": contact in CLOSE_FRIENDS,
    }


def main():
    inbox_dir = INSTAGRAM_INBOX
    if not os.path.isdir(inbox_dir):
        print(f"  ⚠ Instagram inbox not found: {inbox_dir}")
        return

    nodes = []
    edges = []

    # Central node
    nodes.append({"id": "arnvudl", "type": "self", "msg_count": 0, "weight": 0})

    for convo_dir in os.listdir(inbox_dir):
        full_path = os.path.join(inbox_dir, convo_dir)
        if not os.path.isdir(full_path):
            continue
        result = _parse_conversation(full_path)
        if result is None:
            continue

        contact = result["contact"]
        nodes.append({
            "id": contact,
            "type": "close_friend" if result["is_close_friend"] else "contact",
            "msg_count": result["msg_count"],
            "weight": result["weight"],
        })
        edges.append({
            "source": "arnvudl",
            "target": contact,
            "weight": result["weight"],
            "msg_count": result["msg_count"],
        })

    graph = {"nodes": nodes, "edges": edges}

    output_dir = os.path.join(WAREHOUSE, "social_graph")
    os.makedirs(output_dir, exist_ok=True)

    graph_path = os.path.join(output_dir, "graph.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print(f"  ✓ social_graph/graph.json — {len(nodes)} nœuds, {len(edges)} arêtes")

    # Also write as parquet via pandas for warehouse consistency
    df_nodes = pd.DataFrame(nodes)
    df_edges = pd.DataFrame(edges)
    df_nodes.to_parquet(os.path.join(output_dir, "nodes.parquet"), index=False)
    df_edges.to_parquet(os.path.join(output_dir, "edges.parquet"), index=False)
    print(f"  ✓ social_graph/nodes.parquet — {len(df_nodes)} lignes")
    print(f"  ✓ social_graph/edges.parquet — {len(df_edges)} lignes")


if __name__ == "__main__":
    main()
