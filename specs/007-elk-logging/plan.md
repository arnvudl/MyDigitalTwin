# Implementation Plan: Centralized Logging (ELK-compatible)

**Branch**: `docs/architecture-specs` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)

---

## Summary

Replace the file handler's text formatter in `src/ingestion/logger.py` with a JSON formatter using `python-json-logger`. Console output stays human-readable. Add `LoggerAdapter` support for automatic context injection (platform, step). Zero changes to call sites in parsers.

---

## Technical Context

**Library**: `python-json-logger` (pythonjsonlogger)  
**Scope**: `src/ingestion/logger.py` only  
**Format**: NDJSON (one JSON object per line)  
**Console**: unchanged (text format)  
**New dependency**: `python-json-logger` in `requirements.txt`

---

## Constitution Check

- [x] No hardcoded paths — log directory from `config.py` pattern (`data/logs/`)
- [x] Backward-compatible — `get_logger(name)` signature unchanged
- [x] No parser changes required
- [x] Logging failures caught silently — pipeline never crashes on log errors

**No constitution violations.**

---

## Project Structure

```text
src/ingestion/
└── logger.py          ← replace file handler formatter; add JSON formatter; add get_logger_with_context()

requirements.txt       ← add python-json-logger
```

---

## Implementation Phases

### Phase 1: JSON File Formatter

**Output**: `logger.py` with JSON file handler  
**Dependencies**: None

Replace `_FILE_FMT` with `pythonjsonlogger.jsonlogger.JsonFormatter`:

```python
from pythonjsonlogger import jsonlogger

_JSON_FMT = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
# Apply to file handler instead of _FILE_FMT
fh.setFormatter(_JSON_FMT)
```

Console handler keeps `_CONSOLE_FMT` (unchanged).

---

### Phase 2: Context Injection

**Output**: `get_logger_with_context()` function for platform-aware logging  
**Dependencies**: Phase 1

```python
def get_logger_with_context(name: str, **context) -> logging.LoggerAdapter:
    logger = get_logger(name)
    return logging.LoggerAdapter(logger, extra=context)
```

Usage in parsers (optional — existing `get_logger()` still works):
```python
log = get_logger_with_context(__name__, platform="SPOTIFY", step="transform")
log.info("Processing started", extra={"record_count": len(df)})
```

---

### Phase 3: Validation

**Output**: Verified JSON output  
**Dependencies**: Phase 1–2

1. Run ingestion on one platform
2. `cat data/logs/ingestion_*.log | jq '.' > /dev/null` — must exit 0
3. Verify required fields present: `timestamp`, `level` (or `levelname`), `name`, `message`

---

## Architecture Decisions

- **`python-json-logger` over `structlog`**: No call-site changes required; structlog would require rewriting all `logger.info()` calls
- **`LoggerAdapter` for context**: Cleanest way to inject platform/step without changing existing call patterns
- **NDJSON**: ELK-compatible, `jq`-friendly, handles streaming
- **Console stays text**: JSON on console is unreadable during development
