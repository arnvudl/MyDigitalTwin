# Tasks: Centralized Logging (ELK-compatible)

**Input**: Design documents from `specs/007-elk-logging/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

---

## Phase 1: JSON File Formatter

- [ ] T001 Add `python-json-logger` to `requirements.txt`
- [ ] T002 In `src/ingestion/logger.py`: import `pythonjsonlogger.jsonlogger.JsonFormatter`, replace `_FILE_FMT` with `JsonFormatter(fmt="%(asctime)s %(levelname)s %(name)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")`, apply to file handler — keep `_CONSOLE_FMT` for console handler unchanged

**Checkpoint**: `python -c "from src.ingestion.logger import get_logger; get_logger('test').info('ok')"` — log file contains valid JSON ✅

---

## Phase 2: Context Injection

- [ ] T003 Add `get_logger_with_context(name: str, **context) -> logging.LoggerAdapter` function to `src/ingestion/logger.py` — wraps `get_logger(name)` in a `logging.LoggerAdapter` with the provided context dict as `extra`

**Checkpoint**: `get_logger_with_context("test", platform="SPOTIFY").info("started")` produces JSON with `platform` field ✅

---

## Phase 3: Validation

- [ ] T004 Run `python -c "from src.ingestion.logger import get_logger; get_logger('validate').info('test')"` then validate with `cat data/logs/ingestion_*.log | python -c "import sys,json; [json.loads(l) for l in sys.stdin]"` — must not raise
- [ ] T005 Verify each JSON entry contains `asctime` (or `timestamp`), `levelname`, `name`, `message` fields
- [ ] T006 Run existing unit tests: `pytest -m unit -v` — confirm no test breaks due to logger changes

**Checkpoint**: JSON output valid, required fields present, unit tests pass ✅

---

## Dependencies & Execution Order

```
T001 → T002 → T003 → T004 → T005 → T006
```

T001 and T002 must run before T003 (need the library installed).

---

## Summary

| Phase | Scope | Tasks | Gate |
|-------|-------|-------|------|
| 1 — JSON Formatter | logger.py | T001–T002 | Log file contains valid JSON |
| 2 — Context | logger.py | T003 | LoggerAdapter with context works |
| 3 — Validation | validation | T004–T006 | JSON valid, tests pass |

**Total**: 6 tasks | **MVP scope**: T001–T002 (JSON formatter only)

---

## Command Reference

```bash
# Install library
pip install python-json-logger

# Smoke test
python -c "from src.ingestion.logger import get_logger; get_logger('test').info('hello')"

# Validate JSON output
cat data/logs/ingestion_$(date +%Y-%m-%d).log | python -c "import sys,json; [json.loads(l) for l in sys.stdin]; print('OK')"

# With jq
cat data/logs/ingestion_*.log | jq '.' > /dev/null && echo "Valid JSON"
```
