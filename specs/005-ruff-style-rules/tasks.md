# Tasks: Ruff Style Rules

**Input**: Design documents from `specs/005-ruff-style-rules/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

---

## Phase 1: Audit

- [ ] T001 Run `ruff check src/ app/ tests/ --select E,F,I,UP --statistics` and record the violation count per rule code

**Checkpoint**: Violation inventory captured ✅

---

## Phase 2: Fix Violations & Update Config

- [ ] T002 Run `ruff check src/ app/ tests/ --select I --fix` to auto-fix all import ordering violations
- [ ] T003 Run `ruff check src/ app/ tests/ --select UP --fix` to auto-fix all pyupgrade violations
- [ ] T004 Run `ruff check src/ app/ tests/ --select F --fix` to auto-fix Pyflakes violations; manually review any removed imports that might be load-order side effects
- [ ] T005 Run `ruff format src/ app/ tests/` to fix E-category formatting violations
- [ ] T006 Update `pyproject.toml` `[tool.ruff.lint].select` to `["E", "F", "I", "UP"]`
- [ ] T007 Run `ruff check src/ app/ tests/` — fix any remaining violations manually; add `# noqa: <code>` only for intentional suppressions with a comment explaining why
- [ ] T008 Run `pytest -m unit -v` — confirm all unit tests still pass after style fixes

**Checkpoint**: `ruff check src/ app/ tests/` exits 0, all unit tests pass ✅

---

## Phase 3: CI Verification

- [ ] T009 Verify `.github/workflows/ci.yml` runs `ruff check` — confirm the extended rules are covered by existing CI step (no new step needed)

**Checkpoint**: CI passes with extended ruff rules ✅

---

## Dependencies & Execution Order

```
T001 (audit) → T002–T005 (fixes, can be batched) → T006 (config update) → T007 (remaining) → T008 (tests) → T009 (CI check)
```

T002–T005 can be run in sequence with `&&` as a single operation.

---

## Summary

| Phase | Scope | Tasks | Gate |
|-------|-------|-------|------|
| 1 — Audit | Statistics | T001 | Violation count known |
| 2 — Fix & Config | src/, app/, tests/ + pyproject.toml | T002–T008 | ruff exits 0, tests pass |
| 3 — CI | ci.yml | T009 | CI green |

**Total**: 9 tasks | **MVP scope**: T001–T008

---

## Command Reference

```bash
# Audit
ruff check src/ app/ tests/ --select E,F,I,UP --statistics

# Auto-fix all fixable violations
ruff check src/ app/ tests/ --select I,UP,F --fix
ruff format src/ app/ tests/

# Verify clean
ruff check src/ app/ tests/

# Regression check
pytest -m unit -v
```
