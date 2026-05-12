# Tasks: Architecture Decision Records (ADRs)

**Input**: Design documents from `specs/004-adrs/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

**Organization**: Phase 1 (template + ADR) → Phase 2 (CONTRIBUTING.md)

---

## Phase 1: Template & First ADR

- [ ] T001 Create `docs/adr/` directory
- [ ] T002 Create `docs/adr/template.md` with MADR sections: Title, Date, Status, Context, Decision, Consequences, Alternatives Considered — include inline guidance comments in each section
- [ ] T003 Create `docs/adr/001-delta-lake-write-strategy.md` documenting the two-pattern Delta write rule: MERGE INTO for incremental tables, delete+append for computed tables; include alternatives considered (full overwrite, append-only) and consequences

**Checkpoint**: `docs/adr/` contains `template.md` and `001-delta-lake-write-strategy.md` ✅

---

## Phase 2: CONTRIBUTING.md

- [ ] T004 Create or update `CONTRIBUTING.md` to add an "Architecture Decision Records" section explaining: when an ADR is required, how to use the template, status lifecycle (Proposed → Accepted → Superseded), and that ADRs are never deleted

**Checkpoint**: `CONTRIBUTING.md` contains "ADR" keyword and links to `docs/adr/` ✅

---

## Dependencies & Execution Order

```
T001 → T002 → T003
T004 — independent (can run in parallel with T001–T003)
```

---

## Summary

| Phase | Scope | Tasks | Gate |
|-------|-------|-------|------|
| 1 — Template & ADR | docs/adr/ | T001–T003 | 2 files created, readable |
| 2 — CONTRIBUTING | CONTRIBUTING.md | T004 | ADR section present |

**Total**: 4 tasks | **MVP scope**: T001–T003 (template + first ADR)
