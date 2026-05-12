# Agent Boundaries: MyDigitalTwin

This document defines which agent is responsible for which code modules in MyDigitalTwin. Use this guide to understand ownership, dependencies, and hand-off points between agents.

---

## 1. Ingestion Lead

**Responsible for:** Data extraction and normalization  
**Modules:** `src/ingestion/`  
**Artifacts:** Standardized tables in `data/processed/`

### Ownership Boundaries

- `src/ingestion/base.py` — ParserBase class and interfaces
- `src/ingestion/parsers/[platform].py` — Platform-specific parsers (Instagram, Spotify, Google, etc.)
- `src/ingestion/run_all.py` — Central ingestion orchestrator
- `src/ingestion/logger.py` — Logging utilities
- `tests/schemas/[platform].py` — Pandera data quality schemas for ingestion output
- `tests/unit/test_parsers.py` — Unit tests for parser logic

### Deliverables

1. **Parser files** for each platform (extend ParserBase)
   - `extract()` — Parse raw GDPR zip/JSON/HTML
   - `transform()` — Validate, deduplicate, map columns
   - `load()` — Write to `data/processed/[PLATFORM]/`

2. **Schema definitions** (Pandera)
   - Define expected columns, types, cardinality
   - Validate 100% of output before handoff to Analytics Lead

3. **Unit test coverage**
   - Test each parser independently
   - Test edge cases (malformed data, missing fields)

### Dependencies

- **Upstream:** None (first step in pipeline)
- **Downstream:** Analytics Lead (reads from `data/processed/`)
- **External:** GDPR export files in `data/inbox/`

### Hand-off to Analytics Lead

- [ ] Parser produces clean output: `data/processed/[PLATFORM]/`
- [ ] Pandera schema validates 100% of records
- [ ] Unit tests pass: `pytest tests/unit/test_parsers.py -v`
- [ ] No hardcoded paths (all from `config.PROCESSED_DATA`)
- [ ] OVERWRITE strategy documented in `run_all.py`

---

## 2. Analytics Lead

**Responsible for:** Data transformation, ML, and warehouse population  
**Modules:** `src/scripts/`  
**Artifacts:** Analytical tables in `data/warehouse/` (Delta Lake format)

### Ownership Boundaries

- `src/scripts/[NN_description]/[NN_description].ipynb` — Analytical notebooks (01-07)
- `src/scripts/[NN_description]/scripts/` — Supporting Python scripts (if needed)
- `tests/data_quality/test_[table_name].py` — Pandera validations for warehouse output
- `tests/schemas/[platform].py` — Input schemas (defined by Ingestion Lead, validated here)

### Deliverables

1. **Jupyter notebooks** (01-07 numbering)
   - Read from `PROCESSED_DATA` (Ingestion Lead output)
   - Spark SQL, PySpark transformations, ML (CLIP, clustering, ALS, etc.)
   - Write to `WAREHOUSE` using `MERGE INTO` Delta Lake

2. **Warehouse tables** (Delta Lake format)
   - Define key columns (partition key, merge key if applicable)
   - Document table purpose and refresh frequency

3. **Data quality validation** (Pandera)
   - Validate warehouse output matches expected schema
   - Test queries, data distributions, referential integrity

### Dependencies

- **Upstream:** Ingestion Lead (reads from `data/processed/`)
- **Downstream:** Dashboard Lead (reads from `WAREHOUSE`)
- **Internal:** Uses `config.build_spark_session()` and `config.WAREHOUSE` path

### Hand-off to Dashboard Lead

- [ ] Warehouse table populated: `data/warehouse/[TABLE_NAME]`
- [ ] Delta Lake format (not just Parquet)
- [ ] Pandera schema validates 100% of warehouse records
- [ ] Data quality tests pass: `pytest tests/data_quality/test_[table_name].py -v`
- [ ] Notebook idempotent (can be re-run without breaking prior results)
- [ ] No hardcoded paths or credentials
- [ ] Table schema and merge key documented in notebook

---

## 3. Dashboard Lead

**Responsible for:** Visualization and user interaction  
**Modules:** `app/`  
**Artifacts:** Dash pages and components, static assets

### Ownership Boundaries

- `app/app.py` — Dash entrypoint and page registration
- `app/pages/[feature].py` — Page layout and callbacks
- `app/components/[component].py` — Reusable UI components (navbar, filters, etc.)
- `app/assets/` — CSS, JavaScript, images
- `tests/integration/test_[feature]_dashboard.py` — Dashboard page tests (optional)

### Deliverables

1. **Dash pages** (read-only from warehouse)
   - Query warehouse tables via Spark or Pandas
   - Plotly figures with callbacks
   - Mantine UI components
   - No data writes from dashboard

2. **Shared components** (if applicable)
   - Reusable filters, headers, modals
   - Live in `app/components/`

3. **Styling** (optional)
   - CSS in `app/assets/` following Mantine design system
   - Consistent with existing style.css

### Dependencies

- **Upstream:** Analytics Lead (reads from `data/warehouse/`)
- **Downstream:** End users
- **Internal:** Uses `config.WAREHOUSE` path for data loading

### Requirements

- [ ] **Read-only:** Dashboard never writes to warehouse
- [ ] **Config-aware:** Use `config.WAREHOUSE` for table paths (no hardcoding)
- [ ] **No computation:** Complex transformations happen in Analytics notebooks, not callbacks
- [ ] **Error handling:** Gracefully handle missing/stale data
- [ ] **Performance:** Paginate large datasets, cache queries if needed

---

## 4. Config & Infrastructure (Shared)

**Responsible for:** Configuration, paths, environment detection  
**Modules:** `config.py`, `pyproject.toml`, Docker configuration  
**Artifacts:** Central configuration, build images

### Ownership

- `config.py` — Central runtime config (paths, env detection, `build_spark_session()`)
- `config.yaml` — User-specific settings (generated via Copier)
- `.env` — Secrets and API keys (NOT committed)
- `Dockerfile`, `Dockerfile.app`, `docker-compose.yml` — Container definitions
- `pyproject.toml` — Ruff linting config
- `pytest.ini` — Test configuration

### Constitutional Rules (All Agents Must Follow)

1. **No hardcoded paths** — Import from `config.py`
2. **No secrets in code** — Use `.env` via `python-dotenv`
3. **Delta Lake MERGE only** — Never `.mode("overwrite")` on warehouse
4. **Idempotent operations** — Re-running should be safe
5. **Test separation** — Unit tests fast, data quality tests use warehouse
6. **Docker-first** — Dockerfiles are source of truth

### Shared Utilities

- `build_spark_session(name, **overrides)` — Spark session builder (used by Analytics Lead)
- `WAREHOUSE`, `PROCESSED_DATA`, `INBOX_ROOT` — Path constants (used by all agents)

---

## Communication & Hand-offs

### Ingestion → Analytics

**Trigger:** Ingestion Lead completes parser  
**Hand-off:** Output table in `data/processed/[PLATFORM]/`  
**Acceptance:** Analytics Lead confirms Pandera schema passes on sample data  
**Contract:** 100% validated records, documented OVERWRITE strategy

### Analytics → Dashboard

**Trigger:** Analytics Lead completes notebook  
**Hand-off:** Warehouse table in `data/warehouse/[TABLE_NAME]`  
**Acceptance:** Dashboard Lead confirms table is populated and accessible  
**Contract:** Delta Lake format, documented schema, idempotent notebook

### Cross-Agent Reviews

- **Config changes:** Any agent touching `config.py` must notify others (centralized)
- **Test framework changes:** Any agent modifying pytest.ini must confirm CI still passes
- **Docker changes:** Changes to Dockerfile/docker-compose impact all agents' local development

---

## Collaboration Patterns

### Adding a New Data Source

1. **Ingestion Lead:** Create parser → deliver `data/processed/[PLATFORM]/`
2. **Analytics Lead:** Create exploration notebook → validate with Pandera
3. **Analytics Lead:** Create analytical notebook → deliver `data/warehouse/[TABLE_NAME]`
4. **Dashboard Lead:** Create page showing [TABLE_NAME] data

### Modifying Warehouse Schema

1. **Analytics Lead:** Update warehouse table schema and notebook
2. **Analytics Lead:** Update Pandera schema in `tests/data_quality/`
3. **Analytics Lead:** Run full data quality tests
4. **Dashboard Lead:** Update page queries to match new schema

### Debugging Data Issues

- **Corrupt data in processed/?** → Ingestion Lead debugs parser
- **Schema mismatch in warehouse/?** → Analytics Lead debugs notebook
- **Dashboard shows stale/wrong data?** → Dashboard Lead confirms query + Analytics Lead confirms data in warehouse

---

## Version & Governance

**Document Version**: 1.0  
**Effective Date**: 2026-05-12  
**Updates Require**: Documentation update + team discussion

**Related Documents**:
- `.specify/memory/constitution.md` — Project principles
- `CONTRIBUTING.md` — Contribution guidelines
- `CLAUDE.md` — Claude Code instructions
