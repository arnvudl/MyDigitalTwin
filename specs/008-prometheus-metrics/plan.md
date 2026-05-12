# Implementation Plan: Prometheus Metrics

**Branch**: `docs/architecture-specs` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)

---

## Summary

Add `prometheus_client` instrumentation to the ingestion pipeline (batch mode — write to textfile) and the Dash dashboard (pull mode — `/metrics` endpoint). Enable Spark's built-in Prometheus reporter via configuration. Total scope: one new `src/ingestion/metrics.py` module, one dashboard route addition, one Spark config file.

---

## Technical Context

**Library**: `prometheus_client` (Python official client)  
**Ingestion mode**: `write_to_textfile()` → `data/metrics/ingestion.prom`  
**Dashboard mode**: WSGI `/metrics` endpoint via `make_wsgi_app()`  
**Spark**: Built-in `PrometheusServlet` via `spark.metrics.conf`  
**New dependency**: `prometheus_client` in `requirements.txt`

---

## Constitution Check

- [x] No hardcoded paths — `data/metrics/` via config pattern
- [x] No behavior change to existing pipeline logic — metrics are additive wrappers
- [x] Metrics failure does not crash pipeline (FR-007)
- [x] No change to Delta Lake write patterns

**No constitution violations.**

---

## Project Structure

```text
src/ingestion/
└── metrics.py          ← NEW: Counter, Histogram definitions + helpers

src/ingestion/run_all.py  ← wrap parser calls with metrics (timing + error counting)

app/
└── server.py (or app.py) ← mount /metrics WSGI app on dashboard server

data/metrics/             ← NEW: directory for ingestion.prom textfile output

conf/
└── metrics.properties    ← NEW: Spark metrics configuration (Prometheus reporter)

requirements.txt          ← add prometheus_client
```

---

## Implementation Phases

### Phase 1: Ingestion Metrics Module

**Output**: `src/ingestion/metrics.py` with metric definitions  
**Dependencies**: None

```python
from prometheus_client import Counter, Histogram, write_to_textfile

INGESTION_RECORDS = Counter(
    "ingestion_records_total",
    "Records processed by the ingestion pipeline",
    ["platform", "step"],
)
INGESTION_DURATION = Histogram(
    "ingestion_duration_seconds",
    "Duration of ingestion pipeline steps",
    ["platform", "step"],
)
INGESTION_ERRORS = Counter(
    "ingestion_errors_total",
    "Errors in ingestion pipeline steps",
    ["platform", "step", "error_type"],
)

METRICS_PATH = "data/metrics/ingestion.prom"
```

---

### Phase 2: Instrument Orchestrator

**Output**: `run_all.py` wraps parser calls with metrics  
**Dependencies**: Phase 1

Wrap each parser's `transform()`, `load()`, `move()` with:
- `INGESTION_DURATION.labels(...).time()` context manager
- `INGESTION_RECORDS.labels(...).inc(len(df))` after transform
- `INGESTION_ERRORS.labels(...).inc()` in except blocks
- `write_to_textfile(METRICS_PATH)` at end of run

---

### Phase 3: Dashboard Metrics Endpoint

**Output**: `/metrics` route on dashboard server  
**Dependencies**: Phase 1

Add to `app/server.py` or the Dash app entry point:

```python
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app.server.wsgi_app = DispatcherMiddleware(app.server.wsgi_app, {
    "/metrics": make_wsgi_app()
})
```

Instrument page render duration using `before_request` / `after_request` hooks.

---

### Phase 4: Spark Metrics (Configuration Only)

**Output**: `conf/metrics.properties` with Prometheus reporter enabled  
**Dependencies**: None

```properties
*.sink.prometheussink.class=org.apache.spark.metrics.sink.PrometheusServlet
*.sink.prometheussink.path=/metrics/prometheus
```

Pass to Spark via `--conf spark.metrics.conf=conf/metrics.properties` or add to `spark-defaults.conf` in Docker compose.

---

## Architecture Decisions

- **`write_to_textfile()` for ingestion**: Batch script can't be scraped — textfile collector is the standard solution
- **WSGI middleware for dashboard**: No Dash-specific library needed; standard Werkzeug middleware
- **Spark config only**: No custom Python code for Spark metrics — built-in reporter handles JVM-level metrics
- **`data/metrics/` directory**: Follows existing `data/` convention; excluded from git via `.gitignore`
