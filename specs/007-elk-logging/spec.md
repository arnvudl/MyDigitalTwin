# Feature Specification: Centralized Logging (ELK-compatible)

**Feature Branch**: `docs/architecture-specs`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification pour structurer les logs de l'application (format JSON) afin qu'ils soient compatibles avec une stack centralisée ELK."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query Logs by Platform and Event Type (Priority: P1)

A developer debugging an ingestion failure needs to filter all log entries for a specific platform (e.g., Spotify) within a time range — without grepping through unstructured text files.

**Why this priority**: The current text-format logs require `grep` to extract platform-specific entries. Structured JSON logs enable instant filtering by any field (platform, level, event type) in tools like Kibana, Grafana, or even `jq` locally.

**Independent Test**: Run the ingestion pipeline for one platform, then run `cat data/logs/ingestion_*.log | jq '.platform == "SPOTIFY"'`. All entries must parse as valid JSON and the filter must return only Spotify entries.

**Acceptance Scenarios**:

1. **Given** the ingestion pipeline processes a Spotify GDPR export, **When** the log file is read, **Then** every log entry is valid JSON with at minimum: `timestamp`, `level`, `logger`, `message`, `platform` fields
2. **Given** a developer pipes the log file through `jq`, **When** they filter by `level == "ERROR"`, **Then** only error entries are returned — no parsing failures
3. **Given** Filebeat or Logstash reads from `data/logs/`, **When** it processes the JSON log entries, **Then** no custom parsing rules are required — standard JSON input works out of the box

---

### User Story 2 - Include Structured Context in Every Log Entry (Priority: P2)

A developer reviewing logs after an ingestion run needs to know not just that an error occurred, but which file, which record, and at which pipeline step — without adding debug print statements.

**Why this priority**: Unstructured log messages like `"Error processing file"` are useless in production. Structured context (file path, record count, step name) makes the log actionable.

**Independent Test**: Run the ingestion pipeline with a deliberately malformed input file. The resulting log entry MUST include `file_path`, `step`, and `record_count` fields in the JSON — not embedded in the `message` string.

**Acceptance Scenarios**:

1. **Given** a parser encounters a malformed record, **When** the error is logged, **Then** the JSON entry includes `file_path`, `step`, `error_type`, and `record_count` as top-level fields — not concatenated into `message`
2. **Given** a developer adds a new log call in a parser, **When** they use the standard logger, **Then** the context fields (`platform`, `step`) are automatically included without extra code

---

### Edge Cases

- What if the ELK stack is not deployed? → JSON logs are still useful locally with `jq`. No runtime dependency on ELK.
- What if a log entry cannot be serialized to JSON (e.g., non-serializable object)? → Fall back to string representation; never crash the pipeline due to a logging error
- What about the dashboard logs? → Dashboard is lower priority; focus on ingestion pipeline logs first

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All log entries written to `data/logs/` MUST be valid JSON (one JSON object per line — NDJSON format)
- **FR-002**: Every JSON log entry MUST include: `timestamp` (ISO 8601), `level`, `logger`, `message`, `platform` (when applicable)
- **FR-003**: Error log entries MUST include: `file_path` and `step` as top-level fields when available
- **FR-004**: Console output MAY remain in human-readable format (not JSON) for developer ergonomics
- **FR-005**: The logging change MUST be backward-compatible — no change to `get_logger()` call signature in parsers
- **FR-006**: Log rotation MUST continue to work (daily log files, filename pattern `ingestion_YYYY-MM-DD.log`)
- **FR-007**: Logging failures MUST NOT propagate as exceptions — the pipeline continues even if a log write fails

### Key Entities

- **Structured Log Entry**: A single JSON object written as one line to the log file, containing standard and context fields
- **Log Context**: Platform-specific metadata (platform name, step, file path) automatically attached to log entries
- **NDJSON**: Newline-delimited JSON — one JSON object per line, compatible with ELK Filebeat input

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `cat data/logs/ingestion_*.log | jq '.' > /dev/null` exits 0 — all entries are valid JSON
- **SC-002**: Every log entry contains `timestamp`, `level`, `logger`, `message` fields
- **SC-003**: No change to `get_logger()` call sites in any parser — backward-compatible API
- **SC-004**: Console output remains human-readable (non-JSON) for local development

## Assumptions

- A logger module already exists at `src/ingestion/logger.py` with a `get_logger(name)` function
- The ELK stack is not yet deployed — logs must be compatible but ELK is not a runtime dependency
- `python-json-logger` or equivalent library is acceptable as a new dependency for JSON formatting
- Dashboard logging is out of scope — only `src/ingestion/` pipeline logs are targeted
