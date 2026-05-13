# Data Model: Convert Notebooks to Production Python Scripts

**Feature**: 011-convert-notebooks-python  
**Date**: 2026-05-13

---

## Output Tables (unchanged — already written by notebooks)

These tables already exist in the warehouse. The conversion does not change their schema; it only ensures the write logic is correctly reproduced in `.py` scripts.

### instagram_comments
- **merge key**: `text + timestamp`
- **write pattern**: MERGE (incremental)
- **key columns**: text, media_owner, timestamp, event_date, event_year, event_month, event_hour, event_weekday, char_count, word_count, emoji_count, platform, content_type

### instagram_likes
- **merge key**: `post_url + timestamp`
- **write pattern**: MERGE (incremental)
- **key columns**: timestamp, post_url, event_date, event_year, event_month, event_hour, event_weekday, platform, action_type

### instagram_messages_meta
- **merge key**: `conv_id + sender_anon + timestamp_ms + msg_type`
- **write pattern**: MERGE (incremental)
- **key columns**: conv_id, is_group, participants, sender_anon, timestamp_ms, msg_type, char_count, event_date, event_year, event_month, event_hour, event_weekday, platform

### instagram_saved
- **merge key**: `post_href + timestamp`
- **write pattern**: MERGE (incremental)

### instagram_posts_viewed, instagram_videos_watched, instagram_story_likes
- **merge key**: `timestamp`
- **write pattern**: MERGE (incremental)
- **note**: file may be absent — scripts must handle gracefully (skip + warning)

### instagram_searches
- **merge key**: `query + timestamp`
- **write pattern**: MERGE (incremental)

---

## New Artifacts

### run_pipeline.py (project root)
```
Inputs:   src/scripts/**/*.py (ordered by stage number)
Outputs:  stdout stage-by-stage status
Args:
  (no args)          → run all stages in order
  --stage <name>     → run one stage by script name
  --from <N>         → start from stage N (1-indexed)
  --to <N>           → stop at stage N (inclusive)
```

### validate_outputs.py (project root)
```
Inputs:   data/warehouse/* (Delta tables)
Outputs:  stdout pass/fail per table, exit code 0 or 1
Expectations dict: {
  "instagram_comments":       {"min_rows": 1,  "required_columns": ["text", "timestamp", "platform"]},
  "instagram_likes":          {"min_rows": 1,  "required_columns": ["timestamp", "post_url", "platform"]},
  "instagram_messages_meta":  {"min_rows": 1,  "required_columns": ["conv_id", "timestamp_ms", "msg_type"]},
  ...
}
```

---

## Stage Execution Order (run_pipeline.py)

```
Stage 01 — 01_exploration/instagram.py           Spark 4g
Stage 02 — 01_exploration/google_youtube.py      Spark 6g  ← plus gourmand
Stage 03 — 01_exploration/spotify.py             Spark 4g
Stage 04 — 01_exploration/tiktok.py              Spark 4g
Stage 05 — 01_exploration/twitter.py             Spark 4g
Stage 06 — 01_exploration/netflix.py             Spark 4g
Stage 07 — 02_clusters/01_content_clustering.py  Spark 4g, delta=True
Stage 08 — 02_clusters/02_behavioral_clustering.py Spark 4g
Stage 09 — 02_clusters/03_fusion_visualization.py  Spark 4g
Stage 10 — 03_memory_album/01_visual_embeddings.py Spark 4g, snappy, delta
Stage 11 — 03_memory_album/02_scene_clustering.py  Spark 4g
Stage 12 — 03_memory_album/03_music_matching.py    Spark 4g
Stage 13 — 04_clone/01_extract_corpus.py           ← existant, non converti
Stage 14 — 04_clone/02_build_gemini_corpus.py      ← existant, non converti
Stage 15 — 05_CLIP/00_collect_photos.py             ← existant, non converti
Stage 16 — 05_CLIP/01_clip_embeddings.py            Spark 4g, snappy, delta
Stage 17 — 05_CLIP/02_clip_clustering.py            Spark 4g, delta, .cache()
Stage 18 — 06_social/01_social_graph.py             PAS DE SPARK — pure Python
Stage 19 — 07_psy/01_build_dossier.py               ← existant, non converti
```
