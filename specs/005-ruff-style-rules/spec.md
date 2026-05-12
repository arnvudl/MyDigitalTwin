# Feature Specification: Ruff Style Rules

**Feature Branch**: `docs/architecture-specs`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification pour étendre la configuration de Ruff (pyproject.toml) afin d'imposer des règles de style strictes sur l'ensemble du code."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enforce Consistent Code Style Automatically (Priority: P1)

A developer submitting a PR needs automated feedback that their code follows the project's style conventions — consistent imports, no unused variables, proper string formatting — without relying on manual review comments.

**Why this priority**: Style inconsistencies accumulate over time and make code harder to read. Automated enforcement prevents new debt and eliminates style discussions in PR reviews.

**Independent Test**: Run `ruff check src/ app/ tests/ --select E,F,I,UP` against the current codebase. Count the violations. After the feature is merged, the same command must exit 0 (all violations fixed or rules scoped to only clean code).

**Acceptance Scenarios**:

1. **Given** a developer submits a PR with unused imports, **When** CI runs `ruff check`, **Then** the check fails and lists the file, line, and violation code — the PR cannot merge until fixed
2. **Given** a developer runs `ruff check .` locally, **When** the codebase is clean, **Then** the command exits 0 with no output in under 10 seconds
3. **Given** a developer uses `ruff format` to format a file, **When** `ruff check` runs on the same file, **Then** no formatting-related violations are reported

---

### User Story 2 - Fix Existing Violations Without Blocking the Team (Priority: P2)

A developer enabling stricter rules needs to fix existing violations in a single PR, without requiring other developers to rebase or causing unrelated test failures.

**Why this priority**: Enabling strict rules on a codebase with existing violations blocks CI immediately. A clean migration path (fix violations first, then enable rules) prevents disruption.

**Independent Test**: Run `ruff check src/ app/ tests/ --select E,F,I,UP` before and after the migration PR. The count must drop to 0. No existing tests fail after the style fixes.

**Acceptance Scenarios**:

1. **Given** the ruff configuration is extended with new rule sets, **When** existing violations in the codebase are fixed in the same PR, **Then** `ruff check` exits 0 and no tests fail
2. **Given** the ruff configuration is committed, **When** any developer clones the repo and runs `ruff check .`, **Then** they get the same results — no local configuration drift

---

### Edge Cases

- What if a rule produces false positives in a specific file (e.g., Jupyter-generated code)? → Use `# noqa: <code>` for targeted suppression, or add the path to `ruff`'s `extend-exclude`
- What if the team wants to add more rules later? → The `pyproject.toml` `select` list is the single source of truth — add rule codes there
- What about notebooks (`.ipynb` files)? → Currently excluded from ruff; keep exclusion in place unless explicitly expanding scope

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `pyproject.toml` `[tool.ruff.lint]` MUST select at minimum: `E` (pycodestyle errors), `F` (Pyflakes), `I` (isort), `UP` (pyupgrade)
- **FR-002**: `ruff check src/ app/ tests/` MUST exit 0 after the migration (all violations fixed or suppressed with `# noqa`)
- **FR-003**: The CI workflow MUST run `ruff check` on every PR and block merge on failure
- **FR-004**: `ruff format` MUST be configured and its output consistent with the `ruff check` rules (no conflicting style rules)
- **FR-005**: Notebooks (`.ipynb`) MUST remain excluded from ruff checks
- **FR-006**: Any `# noqa` suppressions added during migration MUST have a code (e.g., `# noqa: E501`) — bare `# noqa` is forbidden

### Key Entities

- **Rule Set**: A named group of Ruff lint rules selected in `[tool.ruff.lint].select` (e.g., `E`, `F`, `I`, `UP`)
- **Violation**: A line of code that fails a selected rule — reported with file path, line number, and rule code
- **Migration PR**: The single PR that enables new rules and fixes all existing violations simultaneously

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `ruff check src/ app/ tests/` exits 0 after the feature is merged
- **SC-002**: CI blocks any future PR that introduces a new ruff violation
- **SC-003**: `ruff check .` completes in under 10 seconds on the full codebase
- **SC-004**: Zero bare `# noqa` suppressions in the codebase after migration

## Assumptions

- Current ruff configuration selects only E9/F63/F7/F82 (critical errors only)
- The codebase has existing style violations that need fixing as part of this feature
- Notebooks remain excluded (separate concern)
- `ruff format` is available (same package as `ruff check`)
