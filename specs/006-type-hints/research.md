# Research: Type Hints (Core Modules)

**Date**: 2026-05-12

## Decision 1: mypy vs. pyright

**Decision**: Use `mypy` with `--ignore-missing-imports`.

**Rationale**: mypy is the most widely adopted Python static type checker. pyright is faster but less commonly used in CI. `--ignore-missing-imports` avoids false positives on third-party packages (pyspark, delta-spark) that lack type stubs.

## Decision 2: Strict vs. non-strict mode

**Decision**: Non-strict mode (`mypy src/ingestion/ --ignore-missing-imports`), not `--strict`.

**Rationale**: `--strict` requires `--disallow-untyped-calls` and `--disallow-any-generics`, which produce excessive noise on a codebase with PySpark and pandas dependencies (these libraries have incomplete stubs). Non-strict enforces return types and parameter types on annotated functions while tolerating unannotated third-party calls.

## Decision 3: Scope — ingestion only vs. full codebase

**Decision**: `src/ingestion/` and `config.py` first; `app/` is out of scope for this feature.

**Rationale**: Ingestion is the highest-risk layer (processes personal GDPR data, writes to `data/processed/`). Dashboard code (`app/`) has less type-safety risk and would require annotating Dash callback signatures which have complex types.

## Decision 4: Handling PySpark types

**Decision**: PySpark types (DataFrame, SparkSession) are not annotated in ingestion parsers because parsers don't use Spark — they only move files. If a future parser needed Spark, use `pyspark.sql.DataFrame` with `# type: ignore[import]`.

## Decision 5: CI integration

**Decision**: Add mypy as an optional CI check (non-blocking initially), promote to blocking after all violations are fixed.

**Rationale**: Adding a new blocking CI check on a codebase that may have type errors would immediately break CI. Run non-blocking first, fix violations, then flip to blocking.
