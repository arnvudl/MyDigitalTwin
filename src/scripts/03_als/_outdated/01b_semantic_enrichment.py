import os
import pandas as pd
import requests
from tqdm import tqdm
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── CONFIG ──────────────────────────────────────────────────────────────────
load_dotenv()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma2:9b")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4")) # 4 est un bon compromis pour 8Go VRAM

# ─── FONCTION D'ENRICHISSEMENT (OLLAMA LOCAL) ────────────────────────────────
def process_item(row):
    title = row['item_title']
    platform = row['platform']
    
    if platform == "netflix":
        prompt = f"""Analyze the Netflix title: "{title}".
Classify it strictly as: [Movie/Series/Anime] | [Main Genre] | [Sub-Genre] | [Mood].
Return ONLY: Category|Genre|Sub-Genre|Vibe. No talk."""
    else:
        prompt = f"""Analyze the Spotify track: "{title}".
Classify it strictly as: [Music] | [Main Genre] | [Sub-Genre/Style] | [Vibe].
Return ONLY: Category|Genre|Sub-Genre|Vibe. No talk."""
    
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0}},
            timeout=20
        )
        if response.status_code == 200:
            meta = response.json().get("response", "").strip()
            line = meta.split('\n')[-1].strip()
            parts = line.split('|')
            if len(parts) < 4: parts = (parts + ["Unknown"] * 4)[:4]
            return {
                "item_title": title, "platform": platform,
                "category": parts[0].strip(), "genre": parts[1].strip(),
                "sub_genre": parts[2].strip(), "atmosphere": parts[3].strip()
            }
    except Exception:
        pass
    
    return {"item_title": title, "platform": platform, "category": "Error", "genre": "Error", "sub_genre": "Error", "atmosphere": "Error"}

# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Trouver la racine du projet (MyDigitalTwin)
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    WAREHOUSE = os.path.join(ROOT_DIR, "data/warehouse")
    input_path = os.path.join(WAREHOUSE, "interactions")
    output_path = os.path.join(WAREHOUSE, "item_metadata.parquet")

    if not os.path.exists(input_path):
        print(f"❌ Erreur : Le dossier {input_path} n'existe pas.")
        exit(1)

    print(f"📥 Lecture des titres...")
    df_all = pd.read_parquet(input_path, engine='pyarrow')
    unique_items = df_all[["item_title", "platform"]].drop_duplicates().to_dict('records')
    
    print(f"🚀 Traitement de {len(unique_items)} items avec {MAX_WORKERS} threads (Modèle: {OLLAMA_MODEL})...")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Lancer les tâches en parallèle
        future_to_item = {executor.submit(process_item, item): item for item in unique_items}
        
        # Récupérer les résultats avec une barre de progression
        for future in tqdm(as_completed(future_to_item), total=len(unique_items)):
            results.append(future.result())

    if results:
        pd.DataFrame(results).to_parquet(output_path, index=False)
        print(f"✅ Terminé ! Stocké dans {output_path}")