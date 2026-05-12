# Research: Centralized Logging (ELK-compatible)

**Date**: 2026-05-12

## Decision 1: JSON formatting library

**Decision**: Use `python-json-logger` (`pythonjsonlogger`) library.

**Rationale**: Drop-in replacement for Python's `logging.Formatter`. Converts all log records to JSON without changing the `logging.getLogger()` API. Widely used, actively maintained, ELK-compatible out of the box. Alternative: `structlog` — more powerful but requires changing call sites (not backward-compatible).

## Decision 2: Console format remains human-readable

**Decision**: Console handler keeps text format; file handler switches to JSON.

**Rationale**: JSON on the console is unreadable for local development. Split formatters (text for console, JSON for file) is the standard approach and satisfies both FR-004 (human-readable console) and FR-001 (JSON in files).

## Decision 3: Context injection strategy

**Decision**: Use `logging.LoggerAdapter` for automatic context injection (platform, step).

**Rationale**: `LoggerAdapter` wraps a logger and automatically merges a context dict into every log record. This requires no change to existing `logger.info("message")` call sites — context is added once at logger creation. Alternative: `extra={}` parameter on every call — too much boilerplate and error-prone.

## Decision 4: NDJSON vs. JSON array

**Decision**: NDJSON (one JSON object per line).

**Rationale**: ELK Filebeat and Logstash both natively support NDJSON. A JSON array would require the entire file to be parsed as one object, which fails for streaming ingestion. NDJSON also works with `jq` line-by-line filtering.

## Decision 5: Log rotation

**Decision**: Keep existing daily rotation pattern (`ingestion_YYYY-MM-DD.log`).

**Rationale**: Already working correctly. ELK Filebeat handles log rotation gracefully. No change needed.
