# Feature Specification: Type Hints (Core Modules)

**Feature Branch**: `docs/architecture-specs`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification pour appliquer un typage statique rigoureux (type hints) aux modules principaux, notamment ParserBase et l'orchestrateur."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Catch Type Errors Before Runtime (Priority: P1)

A developer modifying a parser or the orchestrator needs to know immediately if they've passed the wrong type to a function — without having to run the full ingestion pipeline with real GDPR files.

**Why this priority**: The ingestion pipeline processes large GDPR exports. A type error caught by a static checker saves a 5-10 minute pipeline run and avoids corrupted `data/processed/` output.

**Independent Test**: Run `mypy src/ingestion/ --strict` (or equivalent). The command must exit 0 — no type errors — on the annotated modules.

**Acceptance Scenarios**:

1. **Given** a developer passes a `str` where a `Path` is expected in `ParserBase.move()`, **When** they run the type checker, **Then** the error is reported with the file name, line number, and expected type — before any code runs
2. **Given** a developer adds a new method to a parser, **When** they omit the return type annotation, **Then** the type checker reports the missing annotation
3. **Given** all core modules are annotated, **When** a new developer reads `src/ingestion/base.py`, **Then** they can understand parameter types and return values without reading the implementation body

---

### User Story 2 - Document the Parser Contract Through Types (Priority: P2)

A developer writing a new parser subclass needs to know exactly what methods to implement and what types each method accepts and returns — without reading the existing parsers as examples.

**Why this priority**: `ParserBase` is the contract between the orchestrator and each parser. Without type annotations, developers guess at parameter types and accidentally return incompatible values.

**Independent Test**: Read `src/ingestion/base.py` abstract methods. Every abstract method must have complete parameter types and return type annotations. A developer should be able to implement a new subclass from the base class alone.

**Acceptance Scenarios**:

1. **Given** a developer opens `src/ingestion/base.py`, **When** they read the abstract method signatures, **Then** they see parameter names, types, and return types for every method — no need to check existing parsers
2. **Given** a new parser subclass does not implement a required method, **When** the type checker runs, **Then** it reports the missing implementation

---

### Edge Cases

- What about config.py (runtime path detection)? → Annotate public functions; skip dynamic `os.environ` internals where types are `str | None` by definition
- What about Spark DataFrames in notebooks? → Notebooks are excluded — type hints apply to `src/ingestion/` and `app/` only
- What if a function legitimately returns `Any`? → Use `Any` explicitly with a comment explaining why — `Any` is allowed but must be intentional

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All public functions and methods in `src/ingestion/base.py` MUST have complete parameter and return type annotations
- **FR-002**: All public functions and methods in `src/ingestion/run_all.py` (orchestrator) MUST have complete parameter and return type annotations
- **FR-003**: All public functions and methods in each parser file (`src/ingestion/parsers/*.py`) MUST have complete parameter and return type annotations
- **FR-004**: All public functions in `config.py` MUST have return type annotations
- **FR-005**: `mypy src/ingestion/ --ignore-missing-imports` MUST exit 0 after the feature is merged
- **FR-006**: `Any` type MUST only be used with an inline comment explaining why a more specific type is not possible

### Key Entities

- **Type Annotation**: A Python `param: Type` or `-> ReturnType` declaration on a function signature
- **Static Type Checker**: A tool (mypy or pyright) that verifies type correctness without running the code
- **Parser Contract**: The set of abstract methods in `ParserBase` — made explicit by type annotations

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `mypy src/ingestion/ --ignore-missing-imports` exits 0
- **SC-002**: Every abstract method in `ParserBase` has complete type annotations (100% coverage on abstract methods)
- **SC-003**: Zero unannotated public functions in `src/ingestion/` after the feature is merged
- **SC-004**: A new parser can be implemented using only `base.py` as reference — no need to consult existing parsers for type information

## Assumptions

- `mypy` is not currently in `requirements.txt` — it will need to be added
- Notebooks (`src/scripts/`) are excluded from type checking
- Dashboard code (`app/`) is lower priority — annotate `src/ingestion/` first
- PySpark types (DataFrame, SparkSession) are not annotated — these live in notebooks, not in the ingestion layer
- `config.py` functions use `Path` return types where applicable
