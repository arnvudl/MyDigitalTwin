"""Orchestrate the MyDigitalTwin analytical pipeline.

Usage:
    python run_pipeline.py                    # run all stages
    python run_pipeline.py --stage instagram  # run one stage by script name
    python run_pipeline.py --from 7 --to 9   # run stages 7-9 (1-indexed)
"""

import argparse
import subprocess
import sys
import os

STAGES = [
    (1,  "01_exploration/instagram.py"),
    (2,  "01_exploration/google_youtube.py"),
    (3,  "01_exploration/spotify.py"),
    (4,  "01_exploration/tiktok.py"),
    (5,  "01_exploration/twitter.py"),
    (6,  "01_exploration/netflix.py"),
    (7,  "02_clusters/01_content_clustering.py"),
    (8,  "02_clusters/02_behavioral_clustering.py"),
    (9,  "02_clusters/03_fusion_visualization.py"),
    (10, "03_memory_album/01_visual_embeddings.py"),
    (11, "03_memory_album/02_scene_clustering.py"),
    (12, "03_memory_album/03_music_matching.py"),
    (13, "04_clone/01_extract_corpus.py"),
    (14, "04_clone/02_build_gemini_corpus.py"),
    (15, "05_CLIP/00_collect_photos.py"),
    (16, "05_CLIP/01_clip_embeddings.py"),
    (17, "05_CLIP/02_clip_clustering.py"),
    (18, "06_social/01_social_graph.py"),
    (19, "07_psy/01_build_dossier.py"),
]

# Docker container mounts scripts at /opt/spark/scripts; locally they're at src/scripts/
_HERE = os.path.dirname(os.path.abspath(__file__))
_LOCAL_SCRIPTS = os.path.join(_HERE, "src", "scripts")
_DOCKER_SCRIPTS = "/opt/spark/scripts"
SCRIPTS_DIR = _LOCAL_SCRIPTS if os.path.isdir(_LOCAL_SCRIPTS) else _DOCKER_SCRIPTS


def _stage_name(rel_path: str) -> str:
    return os.path.splitext(os.path.basename(rel_path))[0]


def run_stage(num: int, rel_path: str) -> None:
    script_path = os.path.join(SCRIPTS_DIR, rel_path)
    name = _stage_name(rel_path)
    print(f"[Stage {num:02d}] Starting: {name}")
    result = subprocess.run([sys.executable, script_path])
    if result.returncode != 0:
        print(f"[Stage {num:02d}] FAILED: {name} (exit code {result.returncode})")
        sys.exit(result.returncode)
    print(f"[Stage {num:02d}] Done:    {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MyDigitalTwin pipeline runner")
    parser.add_argument("--stage", help="Run a single stage by script filename (without .py)")
    parser.add_argument("--from", dest="from_stage", type=int, help="Start from stage N (1-indexed)")
    parser.add_argument("--to", dest="to_stage", type=int, help="Stop at stage N (inclusive)")
    args = parser.parse_args()

    selected = STAGES

    if args.stage:
        selected = [(n, p) for n, p in STAGES if _stage_name(p) == args.stage]
        if not selected:
            names = [_stage_name(p) for _, p in STAGES]
            print(f"Unknown stage '{args.stage}'. Available: {', '.join(names)}")
            sys.exit(1)
    elif args.from_stage or args.to_stage:
        lo = args.from_stage or 1
        hi = args.to_stage or STAGES[-1][0]
        selected = [(n, p) for n, p in STAGES if lo <= n <= hi]

    for num, rel_path in selected:
        run_stage(num, rel_path)

    print("Pipeline complete.")


if __name__ == "__main__":
    main()
