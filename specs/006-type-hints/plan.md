# Implementation Plan: Type Hints (Core Modules)

**Branch**: `docs/architecture-specs` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)

---

## Summary

Add complete type annotations to `src/ingestion/base.py`, `src/ingestion/run_all.py`, all 6 parser files, and public functions in `config.py`. Add `mypy` to `requirements.txt` and CI. Target: `mypy src/ingestion/ --ignore-missing-imports` exits 0.

---

## Technical Context

**Type Checker**: mypy with `--ignore-missing-imports`  
**Scope**: `src/ingestion/` (base.py, run_all.py, parsers/*.py), `config.py`  
**Excluded**: `src/scripts/` (notebooks), `app/` (dashboard)  
**New dependency**: `mypy` in `requirements.txt`

---

## Constitution Check

- [x] No hardcoded paths
- [x] Annotations are additive — no behavior change
- [x] No new runtime dependencies — mypy is a dev/CI dependency only
- [x] Notebooks excluded from type checking

**No constitution violations.**

---

## Project Structure

```text
src/ingestion/
├── base.py          ← annotate ParserBase class fully
├── run_all.py       ← annotate orchestrator functions
├── parsers/
│   ├── instagram.py ← annotate transform(), load(), move()
│   ├── spotify.py   ← annotate transform(), load(), move()
│   ├── google.py    ← annotate transform(), load(), move()
│   ├── netflix.py   ← annotate transform(), load(), move()
│   ├── tiktok.py    ← annotate transform(), load(), move()
│   └── twitter.py   ← annotate transform(), load(), move()
config.py            ← annotate public functions (build_spark_session, paths)
requirements.txt     ← add mypy
.github/workflows/ci.yml ← add mypy step (non-blocking initially)
```

---

## Implementation Phases

### Phase 1: base.py Annotations

**Output**: Fully annotated `ParserBase` class  
**Dependencies**: None

Key types to define:
- `move(self) -> None`
- `transform(self) -> pd.DataFrame` (or per-parser specific return)
- `load(self, df: pd.DataFrame) -> None`
- Abstract method signatures with `abc.abstractmethod`
- `__init__` parameters: `source_folder: str | Path`, etc.

---

### Phase 2: Parser Annotations

**Output**: All 6 parser files annotated  
**Dependencies**: Phase 1 (inherits from annotated base)

Each parser: annotate `__init__`, `transform()`, `load()`, any helper methods.
Return type for `transform()` is `pd.DataFrame`.

---

### Phase 3: Orchestrator & Config

**Output**: `run_all.py` and `config.py` annotated  
**Dependencies**: Phase 2

- `run_all.py`: entry point functions, loop variables
- `config.py`: `build_spark_session() -> SparkSession`, path constants typed as `Path`

---

### Phase 4: CI Integration

**Output**: `mypy` in requirements and CI  
**Dependencies**: Phase 1–3

1. Add `mypy` to `requirements.txt`
2. Add to `.github/workflows/ci.yml`:
   ```yaml
   - name: Type check
     run: mypy src/ingestion/ --ignore-missing-imports
     continue-on-error: true  # non-blocking until all violations fixed
   ```
3. Once `mypy` exits 0: remove `continue-on-error`

---

## Architecture Decisions

- **Non-strict mypy**: Avoids false positives from PySpark/pandas incomplete stubs
- **`--ignore-missing-imports`**: Required for pyspark, delta-spark, pandera which lack complete type stubs
- **Non-blocking CI initially**: Prevents CI breakage while fixing violations; flip to blocking after clean run
- **`pd.DataFrame` as primary return type**: Parsers operate on pandas DataFrames, not Spark DataFrames
