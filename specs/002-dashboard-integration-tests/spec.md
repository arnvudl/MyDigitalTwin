# Feature Specification: Dashboard Integration Tests

**Feature Branch**: `002-dashboard-integration-tests`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification pour ajouter des tests d'intégration au Dashboard (dossier app/) avec dash[testing] et le fixture dash_duo."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify Pages Load Without Errors (Priority: P1)

A developer needs confidence that every page of the Dashboard renders without runtime errors after code changes. Currently, regressions are only caught manually when someone opens the browser.

**Why this priority**: A broken page that fails to load is the most critical regression — it renders a feature completely unusable and is invisible without automated checks.

**Independent Test**: Run the integration test suite; every registered page receives an HTTP GET and the response must be 200 with a non-empty body. Delivers immediate regression detection for any page break.

**Acceptance Scenarios**:

1. **Given** the dashboard is started in test mode, **When** a test client requests any registered page URL (`/`, `/clusters`, `/spotify`, `/netflix`, `/social`, `/photos`, `/memory-album`, `/psy`, `/timeline`, `/inventory`), **Then** the response status is 200 and the page body is non-empty
2. **Given** a page component raises an unhandled exception, **When** the test client requests that page, **Then** the test fails and reports the page name and exception
3. **Given** the test suite runs in CI, **When** all pages load successfully, **Then** the suite exits with code 0 in under 60 seconds

---

### User Story 2 - Verify Key Callbacks Respond Correctly (Priority: P2)

A developer needs assurance that interactive elements (dropdowns, filters, date pickers) trigger the correct callback and return a valid Plotly figure or component — not an error panel.

**Why this priority**: Pages loading silently is not enough — broken callbacks produce blank charts or error banners that are invisible at the HTTP layer but break the user experience.

**Independent Test**: Simulate a dropdown interaction on the Clusters page and assert the graph output is a non-empty Plotly figure dict. Delivers confidence that the most-used interactive flow works end-to-end.

**Acceptance Scenarios**:

1. **Given** the Clusters page is loaded, **When** a cluster is selected from the dropdown, **Then** the graph callback returns a non-null Plotly figure with at least one trace
2. **Given** the Spotify page is loaded, **When** a time range filter is applied, **Then** the top-artists chart updates without raising an exception
3. **Given** a callback receives an invalid or empty input, **When** the callback executes, **Then** it returns an empty-state component rather than raising an unhandled exception

---

### User Story 3 - Validate Navigation Bar Links (Priority: P3)

A developer needs to confirm that all navigation links in the navbar resolve to existing pages and that none return a 404.

**Why this priority**: Dead navigation links erode trust and are easy to introduce when renaming routes. Automated validation prevents silent link rot.

**Independent Test**: Extract all `href` values from the navbar component and assert each one matches a registered Dash page path. Completely independent of data availability.

**Acceptance Scenarios**:

1. **Given** the navbar is rendered, **When** all link `href` attributes are extracted, **Then** each href matches a path registered in `dash.page_registry`
2. **Given** a page is removed but the navbar link is not updated, **When** the test runs, **Then** the test fails and names the broken link

---

### Edge Cases

- What happens when the warehouse tables are empty or missing? → Tests must mock or stub warehouse reads so they do not depend on real data presence
- What happens when a callback depends on a Spark session that is not running? → Dashboard callbacks must be tested with pre-loaded Pandas DataFrames, not live Spark queries
- What if a page has no registered callbacks? → Page-load tests still apply; callback tests are skipped for pages without interactive elements

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The test suite MUST cover all 10 registered dashboard pages with at minimum a page-load test
- **FR-002**: Each page-load test MUST assert HTTP status 200 and non-empty response body
- **FR-003**: Callback tests MUST simulate user interactions (dropdown selection, filter change) and assert the output type and non-null content
- **FR-004**: Tests MUST NOT depend on a live Spark session or real warehouse data — all warehouse reads MUST be replaced with static fixtures
- **FR-005**: The test suite MUST be executable via `pytest tests/integration/ -v` with no additional setup beyond `pip install dash[testing]`
- **FR-006**: Tests MUST be tagged with `@pytest.mark.integration` to allow selective execution separate from unit and data-quality tests
- **FR-007**: The CI pipeline MUST execute integration tests on every pull request targeting `main`
- **FR-008**: Test execution time MUST remain under 120 seconds for the full suite

### Key Entities

- **Dashboard Page**: A Dash page module registered via `dash.register_page()`, identified by its URL path and layout function
- **Callback**: A Dash callback function decorated with `@callback`, taking Input components and returning Output components
- **Fixture**: A static dataset (Pandas DataFrame or dict) that substitutes real warehouse data during testing
- **Test Client**: The `dash_duo` fixture or Flask test client used to interact with the running dashboard in a headless browser or HTTP mode

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of registered dashboard pages have at least one automated test that validates they load without error
- **SC-002**: The integration test suite completes in under 120 seconds on a standard CI runner
- **SC-003**: Any future page-load regression is caught automatically within the same CI run that introduces it (0 regressions reach `main` undetected)
- **SC-004**: At least 3 interactive callbacks are covered by automated interaction tests (one per P1/P2/P3 page)
- **SC-005**: The test suite runs without requiring a live Spark cluster, warehouse data, or external API credentials

## Assumptions

- The dashboard is a Dash multi-page application using `dash.register_page()` for all 10 pages
- `dash[testing]` and the `dash_duo` fixture require a compatible browser driver (ChromeDriver); CI is assumed to have Chrome available
- Warehouse reads in page modules can be wrapped in a function that is mockable/patchable at test time; direct module-level reads that execute at import time will require refactoring
- Spark sessions are not used inside the Dash app at runtime — data is read as Parquet/Delta via Pandas at startup
- The existing `pytest.ini` marker configuration will be extended to register the `integration` marker
