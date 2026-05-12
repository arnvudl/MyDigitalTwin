# Feature Specification: Secret Manager

**Feature Branch**: `docs/architecture-specs`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification pour supprimer la dépendance aux fichiers .env locaux et migrer la gestion des identifiants vers un Secret Manager (ex: Vault ou AWS Secrets)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rotate API Keys Without Touching Code or Config Files (Priority: P1)

A developer needs to rotate a compromised Spotify API key without modifying any file on disk — to prevent the old key from appearing in git history, editor swap files, or CI logs.

**Why this priority**: `.env` files are frequently leaked via accidental git commits, editor auto-save to cloud, or CI log exposure. Centralizing secrets in a Secret Manager removes the secret from the filesystem entirely.

**Independent Test**: Delete the `.env` file from the machine. Run the dashboard. It must start successfully by fetching `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` from the Secret Manager — with no `.env` file present and no code change.

**Acceptance Scenarios**:

1. **Given** no `.env` file exists on disk, **When** the application starts, **Then** it fetches all required secrets from the Secret Manager and operates normally
2. **Given** an API key is rotated in the Secret Manager, **When** the application restarts, **Then** it uses the new key without any file or code change
3. **Given** the Secret Manager is unavailable at startup, **When** the application starts, **Then** it fails with a clear error identifying which secret could not be retrieved — not a cryptic `AttributeError`

---

### User Story 2 - Local Development Without a Cloud Secret Manager (Priority: P2)

A developer working locally without access to a production Secret Manager needs to use `.env` files as a fallback — without changing the secret retrieval code.

**Why this priority**: Requiring a running Vault or AWS Secrets instance for local development creates friction. The secret retrieval layer must be transparent — `.env` files for local, Secret Manager for CI/prod.

**Independent Test**: Run the application with a `.env` file present and no Secret Manager configured. Verify it reads secrets from `.env` (current behavior) without any error or deprecation warning.

**Acceptance Scenarios**:

1. **Given** a `.env` file is present and no Secret Manager URL is configured, **When** the application starts, **Then** secrets are loaded from `.env` (backward-compatible behavior)
2. **Given** both a `.env` file and a Secret Manager are configured, **When** the application starts, **Then** the Secret Manager takes priority over `.env`

---

### Edge Cases

- What if a secret is missing from both `.env` and Secret Manager? → Application fails at startup with a list of missing secrets — not at the first usage of each secret
- What if the Secret Manager returns a stale cached value? → Cache TTL is configurable; default is 5 minutes; `REFRESH_SECRETS=1` forces re-fetch
- What about secrets in Docker Compose? → Docker Compose `secrets:` syntax is an alternative — not in scope for this spec (separate concern)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST be able to start with zero `.env` file if a Secret Manager URL is configured
- **FR-002**: The secret retrieval layer MUST fall back to `.env` when no Secret Manager is configured
- **FR-003**: Secret Manager priority MUST override `.env` when both are present
- **FR-004**: Missing secrets MUST be reported at startup as a list, not one-at-a-time at runtime
- **FR-005**: The secret retrieval API MUST be a single `get_secret(name: str) -> str` function — callers do not know the source
- **FR-006**: Secret Manager authentication MUST use environment-native credentials (IAM role, Vault token, etc.) — no hardcoded credentials
- **FR-007**: The implementation MUST support at minimum one of: HashiCorp Vault, AWS Secrets Manager, or GCP Secret Manager

### Key Entities

- **Secret**: A named string value (API key, token) retrieved at runtime from a secure store — never stored in plaintext on disk or in code
- **Secret Provider**: The backend that stores and serves secrets (Vault, AWS SM, local `.env` fallback)
- **Secret Resolver**: The application layer (`get_secret(name)`) that abstracts the provider — callers don't know the source

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The application starts and operates normally with no `.env` file, when Secret Manager is configured
- **SC-002**: All secret retrieval in the codebase goes through `get_secret()` — zero direct `os.environ.get("SPOTIFY_CLIENT_ID")` calls outside the resolver
- **SC-003**: Missing secret errors are reported at startup as a batch — not scattered across runtime
- **SC-004**: Local development with `.env` continues to work without any configuration change

## Assumptions

- Current secrets: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `TMDB_API_KEY`, `TMDB_ACCESS_TOKEN`, `GEMINI_API_KEY` (if used)
- The project is a personal project — HashiCorp Vault (free, self-hosted) is the preferred Secret Manager over AWS/GCP (requires cloud account)
- A running Vault instance is NOT required for this feature — only the abstraction layer and documentation
- Copier templates generate `.env` for local development — this workflow is preserved as the fallback
- Docker Compose secrets integration is out of scope (separate feature)
