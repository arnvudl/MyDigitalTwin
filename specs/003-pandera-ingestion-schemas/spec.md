# Feature Specification: Pandera Ingestion Schemas

**Feature Branch**: `docs/architecture-specs`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification pour documenter et valider les schémas d'ingestion des API (tests/schemas/) en utilisant pandera.DataFrameSchema."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Catch Malformed Records at Ingestion Boundary (Priority: P1)

A developer running the ingestion pipeline needs immediate feedback when a GDPR export contains unexpected data — wrong column types, missing required fields, out-of-range values — before those records contaminate the warehouse.

**Why this priority**: Silent data corruption is the hardest bug to diagnose. Catching schema violations at the ingestion boundary prevents downstream analytics and dashboard errors caused by bad data.

**Independent Test**: Run the ingestion pipeline against a sample GDPR export with one intentionally malformed record (e.g., null `post_id`, negative `likes`). The pipeline must raise a schema validation error identifying the offending column and row count before writing to `data/processed/`.

**Acceptance Scenarios**:

1. **Given** a GDPR export with a column type mismatch (e.g., `watch_date` as string instead of date), **When** the ingestion pipeline runs, **Then** validation fails with a clear error message naming the column and the expected type
2. **Given** a GDPR export where all records conform to the schema, **When** the ingestion pipeline runs, **Then** validation passes silently and records are written to `data/processed/`
3. **Given** a schema requiring `post_id` to be unique, **When** the export contains duplicates, **Then** validation fails and reports the duplicate count

---

### User Story 2 - Document Expected Schema for Each Platform (Priority: P2)

A developer adding a new data source or debugging a pipeline failure needs a single, authoritative reference for what columns each platform export is expected to produce — column names, types, nullable rules, and value constraints.

**Why this priority**: Without documented schemas, every pipeline failure requires reading raw export files to understand the expected structure. Schemas make this knowledge explicit and shareable.

**Independent Test**: Open `tests/schemas/spotify.py` and verify it contains column definitions with types, nullable rules, and at least one value constraint (e.g., `ms_played >= 0`). The schema file alone must be readable as documentation without running any code.

**Acceptance Scenarios**:

1. **Given** a developer opens `tests/schemas/[platform].py`, **When** they read the file, **Then** they can identify every expected column, its type, whether it is nullable, and any value constraints — without running the pipeline
2. **Given** a new platform is added to the ingestion pipeline, **When** the PR is reviewed, **Then** a corresponding schema file must exist in `tests/schemas/` or the PR is rejected
3. **Given** a schema file exists, **When** a developer queries "what columns does the Netflix export produce?", **Then** `tests/schemas/netflix.py` answers the question completely

---

### User Story 3 - Run Schema Validation in CI on Every PR (Priority: P3)

A developer merging a parser change needs automated confirmation that the parser output still matches the documented schema — without requiring a full warehouse run.

**Why this priority**: Schema drift (parser output diverging from documented schema) is a common source of silent failures. CI enforcement prevents merging parser changes that break the contract.

**Independent Test**: Push a PR that changes a column name in `SpotifyParser.transform()`. The CI data-quality test must fail and block the merge, reporting which schema constraint was violated.

**Acceptance Scenarios**:

1. **Given** a PR modifies a parser's `transform()` output, **When** CI runs `pytest tests/data_quality/ -v`, **Then** schema validation executes and either passes (no drift) or fails (drift detected) before the PR can be merged
2. **Given** all parsers produce output conforming to their schemas, **When** CI runs the data-quality suite, **Then** all tests pass in under 5 minutes
3. **Given** a schema constraint is deliberately relaxed (e.g., making a required field nullable), **When** the PR is reviewed, **Then** the schema change is visible as a diff in `tests/schemas/[platform].py` — not hidden in parser code

---

### Edge Cases

- What if a platform export has no records (empty file)? → Schema validation must pass on empty DataFrames (0 rows valid)
- What if a column is added by the platform provider in a future export? → Schema must not fail on extra columns (use `strict=False` by default); extra columns are allowed but not required
- What if the same platform has multiple export formats (e.g., Spotify streaming vs. liked songs)? → Each logical table gets its own schema definition in `tests/schemas/[platform].py`

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A Pandera schema MUST exist in `tests/schemas/[platform].py` for every active ingestion parser (Instagram, Spotify, Google, Netflix, TikTok, Twitter)
- **FR-002**: Each schema MUST define column names, data types, and nullable rules for every column produced by the parser's `transform()` method
- **FR-003**: Each schema MUST include at least one value constraint per table (e.g., count ≥ 0, date in valid range, string length > 0) where a meaningful constraint exists
- **FR-004**: Schema validation MUST run as part of `pytest tests/data_quality/` and be tagged `@pytest.mark.data_quality`
- **FR-005**: Schema validation MUST be non-blocking on extra columns (columns present in data but not in schema are allowed)
- **FR-006**: Schema validation MUST fail fast with a human-readable error identifying the column name and violation type
- **FR-007**: The data-quality test suite MUST complete in under 5 minutes for all 6 platforms combined
- **FR-008**: A schema file MUST be created or updated in the same PR as any parser change that modifies the `transform()` output columns

### Key Entities

- **Platform Schema**: A Pandera `DataFrameSchema` definition for one logical table produced by one parser, stored in `tests/schemas/[platform].py`
- **Validation Result**: Pass (data conforms) or Fail (with column name, violation type, and row count) — reported by pytest at the data-quality gate
- **Parser Contract**: The implicit agreement between a parser's `transform()` output and the downstream warehouse schema — made explicit by the Pandera schema file

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of active parsers (6 platforms) have a corresponding Pandera schema file in `tests/schemas/`
- **SC-002**: Schema validation catches 100% of column-type mismatches and missing required fields when tested against intentionally malformed sample data
- **SC-003**: The data-quality test suite completes in under 5 minutes for all platforms combined
- **SC-004**: Any parser PR that changes `transform()` output columns without updating the schema is blocked by CI (0 undetected schema drifts reach `main`)
- **SC-005**: Each schema file is self-documenting — a developer unfamiliar with the platform can understand the expected data structure by reading the schema file alone

## Assumptions

- The 6 active parsers (Instagram, Spotify, Google, Netflix, TikTok, Twitter) are already implemented and produce stable output from `transform()`
- Sample GDPR export files (or synthetic equivalents) are available for each platform to run validation tests against
- The data-quality tests read from `data/processed/[PLATFORM]/` (already written by parsers) — they do not re-run the parsers
- Schema validation is applied to the processed data (after `load()`), not inline during `transform()` — this keeps parsers lightweight
- Extra columns (not in schema) are allowed by default; strict mode is opt-in per schema if needed
