import shutil
from pathlib import Path

from config import PHOTO_SORTING_DIR, PHOTO_SOURCE_DIRS, PROJECT_ROOT

SOURCE_DIRS = [Path(path) for path in PHOTO_SOURCE_DIRS]
DEST_DIR = Path(PHOTO_SORTING_DIR)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def collect_photos(dry_run: bool = True) -> None:
    """
    Scan processed Instagram folders and collect photos for manual CLIP sorting.

    Source:
    - data/processed/INSTAGRAM/...

    Destination:
    - data/processed/INSTAGRAM/CLIP_SORTING/
    """
    found_count = 0
    copied_count = 0

    if not dry_run and not DEST_DIR.exists():
        DEST_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Creation du dossier : {DEST_DIR}")

    print(f"--- Recherche de photos dans {len(SOURCE_DIRS)} sources ---")
    print(f"Racine detectee : {PROJECT_ROOT}")
    print(f"Dossier de tri  : {DEST_DIR}")

    for src_path in SOURCE_DIRS:
        if not src_path.exists():
            print(f"[!] Dossier introuvable (ignore) : {src_path}")
            continue

        print(f"Exploration de : {src_path}...")
        for file in src_path.rglob("*"):
            if file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            found_count += 1

            if dry_run:
                continue

            unique_name = f"{file.parent.name}_{file.name}"
            target_file = DEST_DIR / unique_name

            try:
                shutil.copy2(file, target_file)
                copied_count += 1
            except Exception as exc:
                print(f"Erreur copie {file.name}: {exc}")

    print("\n--- Resultat ---")
    print(f"Photos trouvees : {found_count}")
    if dry_run:
        print("Mode dry-run actif : aucun fichier copie.")
    else:
        print(f"Photos copiees dans {DEST_DIR} : {copied_count}")


if __name__ == "__main__":
    collect_photos(dry_run=False)
