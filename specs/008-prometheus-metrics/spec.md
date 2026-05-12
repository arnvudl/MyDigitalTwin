# Feature Specification: Prometheus Metrics

**Feature Branch**: `docs/architecture-specs`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification pour exposer les métriques de performance via Prometheus pour les pipelines d'ingestion, Spark et le Dashboard."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Monitor Ingestion Pipeline Performance (Priority: P1)

A developer or operator needs to know how many records were processed, how long each parser took, and whether any parsing step failed — without reading log files or adding debug print statements.

**Why this priority**: The ingestion pipeline runs unattended on large GDPR exports. Without metrics, a slow or failing parser goes unnoticed until the downstream dashboard shows wrong data.

**Independent Test**: Run the ingestion pipeline for one platform. Then query `http://localhost:8000/metrics`. The response must include counters for `ingestion_records_total{platform="SPOTIFY"}` and a histogram for `ingestion_duration_seconds{platform="SPOTIFY", step="transform"}`.

**Acceptance Scenarios**:

1. **Given** the ingestion pipeline finishes processing a Spotify export, **When** `http://localhost:8000/metrics` is scraped, **Then** the response includes `ingestion_records_total` with `platform="SPOTIFY"` label and the actual record count
2. **Given** a parser step raises an exception, **When** the metrics endpoint is scraped, **Then** `ingestion_errors_total{platform=..., step=...}` is incremented
3. **Given** Prometheus is configured to scrape the metrics endpoint, **When** a Grafana dashboard queries `ingestion_duration_seconds`, **Then** it returns per-platform, per-step latency histograms

---

### User Story 2 - Monitor Dashboard Request Performance (Priority: P2)

An operator needs to know how long each dashboard page takes to render and how many concurrent users are active — to detect regressions after code changes.

**Why this priority**: The dashboard reads from Delta Lake files on every page load. A slow file read can degrade user experience. Metrics make this visible without adding timing code to every page.

**Independent Test**: Load the dashboard home page in a browser. Then scrape `http://localhost:8000/metrics`. The response must include `dashboard_request_duration_seconds{endpoint="/"}`.

**Acceptance Scenarios**:

1. **Given** a user loads the `/clusters` page, **When** the metrics endpoint is scraped, **Then** `dashboard_request_duration_seconds{endpoint="/clusters"}` has at least one observation
2. **Given** a page render raises an unhandled exception, **When** the metrics endpoint is scraped, **Then** `dashboard_errors_total{endpoint="/clusters"}` is incremented

---

### Edge Cases

- What if Prometheus is not running? → The metrics endpoint still runs independently; no runtime dependency on a Prometheus server
- What if the ingestion pipeline runs as a one-off script (not a server)? → Use `prometheus_client.push_to_gateway()` or write metrics to a text file for scraping
- What about Spark metrics? → Spark has a built-in Prometheus reporter — enable it via `spark.metrics.conf`; no custom code needed

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ingestion pipeline MUST expose `ingestion_records_total` (Counter) with labels `platform`, `step`
- **FR-002**: The ingestion pipeline MUST expose `ingestion_duration_seconds` (Histogram) with labels `platform`, `step`
- **FR-003**: The ingestion pipeline MUST expose `ingestion_errors_total` (Counter) with labels `platform`, `step`, `error_type`
- **FR-004**: The dashboard MUST expose `dashboard_request_duration_seconds` (Histogram) with label `endpoint`
- **FR-005**: Metrics MUST be accessible at a `/metrics` HTTP endpoint in Prometheus text format
- **FR-006**: Metrics collection MUST NOT add more than 5ms overhead per instrumented operation
- **FR-007**: If the metrics endpoint fails to start, the pipeline and dashboard MUST still run normally

### Key Entities

- **Counter**: A metric that only increases — used for total records processed, total errors
- **Histogram**: A metric that records distributions — used for duration measurements with pre-defined buckets
- **Labels**: Dimensions on a metric (platform, step, endpoint) that allow filtering in Prometheus queries
- **Scrape Endpoint**: An HTTP endpoint (`/metrics`) that Prometheus polls at a configurable interval

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After an ingestion run, `ingestion_records_total` reflects the actual record count for the processed platform
- **SC-002**: `ingestion_duration_seconds` histograms are populated for each parser step (transform, load, move)
- **SC-003**: The `/metrics` endpoint responds in under 100ms
- **SC-004**: Dashboard request latency is visible per endpoint without modifying individual page files

## Assumptions

- `prometheus_client` Python library is available as a new dependency
- The ingestion pipeline is not a long-running server — metrics will be pushed to a Pushgateway or written to a text file for batch pipelines
- Spark metrics are enabled via Spark configuration, not custom Python code
- A Prometheus server and Grafana instance are not required at implementation time — the metrics endpoint just needs to exist
