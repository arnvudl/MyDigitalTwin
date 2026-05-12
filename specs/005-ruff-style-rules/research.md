# Research: Ruff Style Rules

**Date**: 2026-05-12

## Decision 1: Which rule sets to enable

**Decision**: Enable `E` (pycodestyle), `F` (Pyflakes), `I` (isort), `UP` (pyupgrade) as the baseline.

**Rationale**: These four cover the most impactful categories without being overly noisy:
- `E`: catches formatting and structural errors (indentation, whitespace, line length)
- `F`: catches logical errors (unused imports, undefined names, unused variables)
- `I`: enforces import ordering — reduces diff noise and merge conflicts
- `UP`: automatically upgrades to modern Python syntax (e.g., `Optional[X]` → `X | None`)

Excluded for now: `N` (naming conventions — too opinionated), `ANN` (annotations — covered by separate type hints spec), `D` (docstrings — excessive for this codebase), `S` (security — valid but separate concern).

## Decision 2: Progressive vs. big-bang enablement

**Decision**: Big-bang — enable all selected rules and fix all violations in one PR.

**Rationale**: Progressive enablement (one rule set at a time) spreads the migration across many PRs and leaves CI inconsistent between them. Since the codebase is small (~20 source files), fixing all violations at once is feasible in a single session.

## Decision 3: line-length

**Decision**: Keep existing `line-length = 120`.

**Rationale**: Already configured. Changing line length would require reformatting most of the codebase.

## Decision 4: `ruff format` vs. Black

**Decision**: Use `ruff format` (not Black).

**Rationale**: Same package, no extra dependency, compatible with `ruff check` rules. Black would require an additional `pyproject.toml` section and potential rule conflicts.
