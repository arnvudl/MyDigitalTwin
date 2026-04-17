import os
import shutil
from pathlib import Path

# --- CONFIGURATION DES CHEMINS ---
# On remonte de 3 niveaux pour atteindre la racine depuis src/scripts/05_CLIP/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

SOURCE_DIRS = [
    PROJECT_ROOT / "data/raw/INSTAGRAM/media",
    PROJECT_ROOT / "data/raw/INSTAGRAM/your_instagram_activity/posts",
    PROJECT_ROOT / "data/raw/INSTAGRAM/your_instagram_activity/messages"
]

# Dossier de destination pour ton tri manuel
DEST_DIR = PROJECT_ROOT / "data/raw/INSTAGRAM/CLIP_SORTING"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

def collect_photos(dry_run=True):
    """
    Parcourt les dossiers sources et identifie les photos.
    Si dry_run=False, copie les photos dans DEST_DIR.
    """
    found_count = 0
    copied_count = 0

    if not dry_run and not DEST_DIR.exists():
        DEST_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Création du dossier : {DEST_DIR}")

    print(f"--- Recherche de photos dans {len(SOURCE_DIRS)} sources ---")
    print(f"Racine détectée : {PROJECT_ROOT}")

    for src_path in SOURCE_DIRS:
        if not src_path.exists():
            print(f"[!] Dossier introuvable (ignoré) : {src_path}")
            continue

        print(f"Exploration de : {src_path}...")

        # rglob pour recherche récursive
        for file in src_path.rglob("*"):
            if file.suffix.lower() in IMAGE_EXTENSIONS:
                found_count += 1

                if not dry_run:
                    # On crée un nom unique pour éviter les collisions (ex: plusieurs '1.jpg')
                    # format: source_parent_nomoriginel.jpg
                    unique_name = f"{file.parent.name}_{file.name}"
                    target_file = DEST_DIR / unique_name

                    try:
                        shutil.copy2(file, target_file)
                        copied_count += 1
                    except Exception as e:
                        print(f"Erreur copie {file.name}: {e}")

    print("\n--- Résultat ---")
    print(f"Photos trouvées : {found_count}")
    if not dry_run:
        print(f"Photos copiées dans {DEST_DIR} : {copied_count}")
    else:
        print(f"ℹ️  C'était un test (dry_run=True).")
        print(f"Modifie le script (ligne 71) pour mettre dry_run=False pour copier réellement.")

if __name__ == "__main__":
    # Change dry_run=False pour copier les fichiers
    collect_photos(dry_run=False)

