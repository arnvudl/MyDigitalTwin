# Implementation Plan: Architecture Decision Records (ADRs)

**Branch**: `docs/architecture-specs` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)

---

## Summary

Create the `docs/adr/` directory with a MADR template and one seed ADR documenting the Delta Lake write strategy. Update `CONTRIBUTING.md` with ADR creation guidelines. Total scope: 3 new files.

---

## Technical Context

**Format**: MADR (Markdown Architectural Decision Records)  
**Storage**: `docs/adr/` directory (version-controlled Markdown)  
**Tooling**: None required — pure Markdown  
**Target Platform**: GitHub (renders Markdown natively)

---

## Constitution Check

- [x] No code changes — documentation only
- [x] No hardcoded paths
- [x] No new dependencies
- [x] `docs/` directory already exists in project root

**No constitution violations.**

---

## Project Structure

```text
docs/
└── adr/
    ├── template.md                    ← MADR template with section guidance
    └── 001-delta-lake-write-strategy.md  ← First ADR: MERGE INTO vs. overwrite

CONTRIBUTING.md                        ← add ADR section (create if absent)
```

---

## Implementation Phases

### Phase 1: Template & First ADR

**Output**: `docs/adr/template.md`, `docs/adr/001-delta-lake-write-strategy.md`  
**Dependencies**: None

**`docs/adr/template.md`** — MADR structure:

```markdown
# NNN. [Short decision title]

**Date**: YYYY-MM-DD  
**Status**: [Proposed | Accepted | Deprecated | Superseded by ADR-NNN]

## Context

[What is the issue that motivates this decision?]

## Decision

[What is the change being proposed or made?]

## Consequences

[What are the positive and negative outcomes of this decision?]

## Alternatives Considered

| Option | Pros | Cons | Reason rejected |
|--------|------|------|-----------------|
| ...    | ...  | ...  | ...             |
```

**`docs/adr/001-delta-lake-write-strategy.md`** — covers:
- Context: GDPR exports change over time; overwrite loses history; MERGE INTO preserves it
- Decision: Two-pattern rule — MERGE INTO for incremental tables, delete+append for computed tables
- Consequences: All warehouse writes must go through `MERGE INTO`; no `.mode("overwrite")` on Delta tables
- Alternatives: Full overwrite (rejected: data loss), append-only (rejected: unbounded growth)

---

### Phase 2: CONTRIBUTING.md Update

**Output**: ADR section in `CONTRIBUTING.md`  
**Dependencies**: Phase 1

**Section to add**:

```markdown
## Architecture Decision Records (ADRs)

Any PR that changes a core architectural pattern (data format, pipeline topology,
new framework dependency, write strategy) must include or reference an ADR.

To create a new ADR:
1. Copy `docs/adr/template.md` to `docs/adr/NNN-short-title.md`
2. Fill all sections
3. Set status to "Proposed" until the PR is merged, then "Accepted"
4. Link the ADR in the PR description

ADRs are never deleted. If a decision changes, mark the old ADR "Superseded by ADR-NNN"
and create a new one.
```

---

## Architecture Decisions

- **MADR over other formats**: No tooling required, GitHub renders it, widely understood
- **Sequential numbering**: Chronological, easy to reference in PR descriptions
- **No automated enforcement**: `CONTRIBUTING.md` convention is sufficient for a solo/small-team project
