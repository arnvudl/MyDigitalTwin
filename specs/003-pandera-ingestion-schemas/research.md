# Research: Pandera Ingestion Schemas

**Date**: 2026-05-12

## Decision 1: Validation timing — at transform() or after load()

**Decision**: Validate after `load()`, reading from `data/processed/[PLATFORM]/` in `tests/data_quality/`.

**Rationale**: Keeps parsers lightweight; validation is a QA gate, not inline logic. Consistent with existing `test_dq_warehouse.py` pattern.

## Decision 2: Strict vs. non-strict mode

**Decision**: `strict=False` by default (extra columns allowed). Opt-in strict per schema.

**Rationale**: Platform providers occasionally add columns to exports. Non-strict prevents false positives on new columns while still catching type/null violations.

## Decision 3: One file per platform vs. one file per table

**Decision**: One file per platform (`tests/schemas/spotify.py`) with multiple schema objects for multiple tables (e.g., `spotify_streams_schema`, `spotify_liked_songs_schema`).

**Rationale**: Mirrors parser structure (one parser per platform). Easy to locate schemas.

## Decision 4: Existing schemas

Some schemas already exist (netflix.py was modified in branch 001). The task is to complete coverage for all 6 platforms and ensure consistency.
