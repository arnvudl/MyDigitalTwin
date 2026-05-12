# Feature Specification: Architecture Decision Records (ADRs)

**Feature Branch**: `docs/architecture-specs`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification pour initialiser le dossier docs/adr/ avec un template MADR et créer le premier enregistrement documentant l'architecture de MyDigitalTwin."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find the Reason Behind an Architecture Decision (Priority: P1)

A developer joining the project or revisiting a past decision needs to understand *why* a specific technology or pattern was chosen — not just that it was chosen. Without an ADR, the rationale is lost when the original contributor leaves or the conversation scrolls out of history.

**Why this priority**: Undocumented decisions get relitigated. Every time a developer questions "why Delta Lake?" or "why Pandera?" the team spends time reconstructing context that could be read in two minutes.

**Independent Test**: Open `docs/adr/001-delta-lake-merge-strategy.md` and verify it contains a clear problem statement, the decision made, the alternatives considered, and the consequences — without needing to read any code.

**Acceptance Scenarios**:

1. **Given** a developer asks "why do we use MERGE INTO instead of overwrite for warehouse tables?", **When** they open `docs/adr/001-delta-lake-merge-strategy.md`, **Then** they find the problem, the decision, the alternatives considered, and the trade-offs — in under 5 minutes of reading
2. **Given** a new ADR needs to be written, **When** the developer copies the MADR template from `docs/adr/template.md`, **Then** all required sections are pre-filled with guidance — no blank-page problem
3. **Given** a developer lists `docs/adr/`, **When** they read the filenames, **Then** they can understand what decision each ADR covers without opening the files

---

### User Story 2 - Enforce ADR Creation as Part of Architecture Changes (Priority: P2)

A PR reviewer needs a way to verify that significant architectural changes are accompanied by a corresponding ADR — so that the decision log stays current as the project evolves.

**Why this priority**: ADR value degrades if new decisions aren't recorded. A process rule (ADR required for arch changes) without tooling support is forgotten under deadline pressure.

**Independent Test**: Open `CONTRIBUTING.md` and find explicit instructions stating that any PR changing core architecture (new data format, new framework dependency, new pipeline pattern) must include or reference an ADR in `docs/adr/`.

**Acceptance Scenarios**:

1. **Given** a PR changes the Delta write pattern, **When** the reviewer checks the PR description, **Then** either a new ADR is linked or an existing ADR is referenced explaining the decision
2. **Given** `CONTRIBUTING.md` is read by a new contributor, **When** they are about to open a PR with an architectural change, **Then** they know an ADR is required before the PR can be merged

---

### Edge Cases

- What if a decision is still being debated? → ADR status field can be set to "Proposed" — not all ADRs need to be "Accepted"
- What if a decision is later reversed? → The original ADR is marked "Superseded" with a link to the new ADR — never deleted
- What if the ADR applies to multiple subsystems? → Scope field in the ADR template captures this; one ADR per decision, not per subsystem

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A `docs/adr/` directory MUST exist with a `template.md` file following the MADR (Markdown Architectural Decision Records) format
- **FR-002**: The MADR template MUST include sections: Title, Status, Context, Decision, Consequences, Alternatives Considered
- **FR-003**: At least one ADR MUST be created documenting the Delta Lake write strategy (MERGE INTO vs. overwrite)
- **FR-004**: Each ADR filename MUST follow the pattern `NNN-short-title.md` (e.g., `001-delta-lake-merge-strategy.md`) for chronological ordering
- **FR-005**: `CONTRIBUTING.md` MUST include a section explaining when an ADR is required and how to create one using the template
- **FR-006**: ADR status values MUST be one of: Proposed, Accepted, Deprecated, Superseded

### Key Entities

- **ADR**: A Markdown file in `docs/adr/` documenting a single architecture decision — its context, the decision made, alternatives considered, and consequences
- **MADR Template**: A pre-filled `template.md` with section headings and inline guidance for authors
- **ADR Status**: The lifecycle state of a decision: Proposed → Accepted → (Deprecated | Superseded)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `docs/adr/` contains at least 1 ADR and 1 template file after the feature is merged
- **SC-002**: A developer unfamiliar with the project can write a new ADR in under 15 minutes using the template
- **SC-003**: `CONTRIBUTING.md` documents the ADR requirement — findable by searching for "ADR" in the file
- **SC-004**: All ADR files follow the `NNN-short-title.md` naming convention with valid status values

## Assumptions

- No existing ADR infrastructure exists in the project (no `docs/adr/` directory currently)
- MADR format is preferred over other ADR formats (lightweight, Markdown-native, no tooling required)
- The first ADR will cover the Delta Lake merge strategy since it is the most recently debated architecture decision
- `CONTRIBUTING.md` already exists or will be created as part of this feature
