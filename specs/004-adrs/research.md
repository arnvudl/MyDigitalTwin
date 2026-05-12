# Research: Architecture Decision Records (ADRs)

**Date**: 2026-05-12

## Decision 1: MADR vs. other ADR formats

**Decision**: Use MADR (Markdown Architectural Decision Records) format.

**Rationale**: MADR is lightweight, purely Markdown-based (no tooling), widely adopted, and has a clear template. Alternatives like RFC-style docs or Y-Statements are heavier. Michael Nygard's original format lacks the "Alternatives Considered" section which is critical for understanding why other options were rejected.

## Decision 2: Storage location

**Decision**: `docs/adr/` directory in the repo root.

**Rationale**: Follows the established convention in most open-source projects. `docs/` already exists in this project. Keeping ADRs in the repo ensures they're version-controlled alongside the code they document.

## Decision 3: Numbering scheme

**Decision**: Sequential 3-digit prefix (`001`, `002`, ...).

**Rationale**: Provides chronological ordering, easy to reference in PRs ("see ADR-003"), and avoids timestamp collisions. 3 digits supports up to 999 ADRs — sufficient for any personal project.

## Decision 4: First ADR topic

**Decision**: Delta Lake write strategy (MERGE INTO vs. overwrite).

**Rationale**: This was the most recently debated and fixed architectural decision (see branch `001-fix-delta-merge`). It affects all 6 parsers and all analytical notebooks. Well-documented in code but not yet in an ADR.

## Decision 5: ADR requirement enforcement

**Decision**: Document in `CONTRIBUTING.md` — no automated enforcement.

**Rationale**: Automated enforcement (PR checks that require an ADR) would need a GitHub Action that's hard to make reliable (how to detect "architectural" changes?). For a solo or small-team project, a documented convention in CONTRIBUTING.md is sufficient.
