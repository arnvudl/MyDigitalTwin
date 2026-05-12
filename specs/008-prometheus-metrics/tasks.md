# Tasks: Prometheus Metrics

**Input**: Design documents from `specs/008-prometheus-metrics/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

---

## Phase 1: Ingestion Metrics Module

- [ ] T001 Add `prometheus_client` to `requirements.txt`
- [ ] T002 Create `src/ingestion/metrics.py` with three metric definitions: `ingestion_records_total` (Counter, labels: platform/step), `ingestion_duration_seconds` (Histogram, labels: platform/step), `ingestion_errors_total` (Counter, labels: platform/step/error_type); define `METRICS_PATH = "data/metrics/ingestion.prom"` and a `flush_metrics()` helper that calls `write_to_textfile(METRICS_PATH)` with `data/metrics/` mkdir
- [ ] T003 Create `data/metrics/` directory and add `data/metrics/*.prom` to `.gitignore`

**Checkpoint**: `python -c "from src.ingestion.metrics import INGESTION_RECORDS, INGESTION_DURATION, INGESTION_ERRORS"` exits 0 ✅

---

## Phase 2: Instrument Orchestrator

- [ ] T004 In `src/ingestion/run_all.py`, wrap each parser step (transform, load, move) with `INGESTION_DURATION.labels(platform=..., step=...).time()` context manager
- [ ] T005 In `src/ingestion/run_all.py`, add `INGESTION_RECORDS.labels(platform=..., step="transform").inc(len(df))` after each successful transform
- [ ] T006 In `src/ingestion/run_all.py`, add `INGESTION_ERRORS.labels(platform=..., step=..., error_type=type(e).__name__).inc()` in exception handlers
- [ ] T007 Call `flush_metrics()` at the end of the orchestrator's main run to write `data/metrics/ingestion.prom`

**Checkpoint**: After ingestion run, `cat data/metrics/ingestion.prom` shows metric lines ✅

---

## Phase 3: Dashboard Metrics Endpoint

- [ ] T008 In the Dash app entry point (`app/app.py` or `app/server.py`), mount `make_wsgi_app()` at `/metrics` using `DispatcherMiddleware`
- [ ] T009 Add `before_request` / `after_request` hooks to track `dashboard_request_duration_seconds` per endpoint

**Checkpoint**: Dashboard running + `curl http://localhost:8050/metrics` returns Prometheus text format ✅

---

## Phase 4: Spark Metrics

- [ ] T010 Create `conf/metrics.properties` with PrometheusServlet configuration for all Spark components (`*.sink.prometheussink.class=...`)
- [ ] T011 Add `--conf spark.metrics.conf=conf/metrics.properties` to Docker Compose spark-master command or `spark-defaults.conf`

**Checkpoint**: Spark master accessible at `http://spark-master:4040/metrics/prometheus` ✅

---

## Dependencies & Execution Order

```
T001 → T002 → T003 (ingestion module setup)
T002 → T004–T007 (orchestrator instrumentation)
T001 → T008–T009 (dashboard, can run in parallel with T004–T007)
T010–T011 (Spark config, independent of all above)
```

---

## Summary

| Phase | Scope | Tasks | Gate |
|-------|-------|-------|------|
| 1 — Module | metrics.py | T001–T003 | Module imports cleanly |
| 2 — Ingestion | run_all.py | T004–T007 | .prom file populated after run |
| 3 — Dashboard | app entry point | T008–T009 | /metrics endpoint responds |
| 4 — Spark | conf/ | T010–T011 | Spark Prometheus endpoint active |

**Total**: 11 tasks | **MVP scope**: T001–T007 (ingestion metrics only)
