# Research: Prometheus Metrics

**Date**: 2026-05-12

## Decision 1: prometheus_client vs. alternatives

**Decision**: Use `prometheus_client` (official Python client).

**Rationale**: Official Prometheus client, well-maintained, supports Counter, Histogram, Gauge, Summary. `statsd` would require a separate daemon. `opentelemetry` is more complex and overkill for a personal project.

## Decision 2: Batch pipeline metrics strategy (push vs. pull)

**Decision**: Use `prometheus_client.write_to_textfile()` for the ingestion pipeline (batch mode).

**Rationale**: The ingestion pipeline is a one-off script, not a long-running server. Prometheus can't scrape a script that exits. Options:
- Pushgateway: Requires running an additional service
- `write_to_textfile()`: Writes metrics to a `.prom` file; Prometheus node exporter's textfile collector picks it up
- Chosen: `write_to_textfile()` to `data/metrics/ingestion.prom` — simpler, no additional service

## Decision 3: Dashboard metrics (pull mode)

**Decision**: Use Dash's Werkzeug server to mount a `/metrics` route via `prometheus_client.make_wsgi_app()`.

**Rationale**: The dashboard runs as a Flask/Werkzeug server (long-running). Prometheus can scrape it directly. No Pushgateway needed.

## Decision 4: Spark metrics

**Decision**: Enable Spark's built-in Prometheus reporter via `spark.metrics.conf`.

**Rationale**: No custom Python code needed. Spark exposes JVM-level metrics (executor memory, GC time, task duration) natively via its metrics system. Configuration only.

## Decision 5: Histogram buckets for duration

**Decision**: Use default `prometheus_client` buckets (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10 seconds).

**Rationale**: Default buckets cover the expected range for file I/O and DataFrame operations (milliseconds to seconds). Custom buckets would require benchmarking first.
