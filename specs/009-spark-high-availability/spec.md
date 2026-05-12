# Feature Specification: Spark High Availability

**Feature Branch**: `docs/architecture-specs`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "Rédige la spécification d'infrastructure pour migrer l'environnement Spark actuel vers un cluster à haute disponibilité (3-master cluster)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Continue Analytical Jobs When the Active Master Fails (Priority: P1)

An operator running a long analytical notebook needs the Spark cluster to survive a master node failure without losing the in-progress job — another master takes over automatically.

**Why this priority**: Without HA, a single master restart causes all running jobs to fail, requiring a full re-run. On notebooks that take 30+ minutes (CLIP embeddings, clustering), this is a significant loss of compute time.

**Independent Test**: Start a Spark cluster with 3 masters. Kill the active master container (`docker stop spark-master-1`). Within 30 seconds, one of the remaining masters MUST become active and the Spark UI must be accessible. A new job submitted to the cluster after the failover MUST complete successfully.

**Acceptance Scenarios**:

1. **Given** 3 master containers are running, **When** the active master is stopped, **Then** another master becomes active within 30 seconds and the cluster accepts new job submissions
2. **Given** a job is running when the active master fails, **When** the standby master takes over, **Then** the running job either completes or fails gracefully with a recoverable error — not a silent hang
3. **Given** all 3 masters are listed in the cluster configuration, **When** a worker or driver connects, **Then** it connects to whichever master is currently active without manual reconfiguration

---

### User Story 2 - Deploy the HA Cluster With a Single Command (Priority: P2)

A developer setting up the environment from scratch needs to start the entire HA cluster (3 masters + workers) with one command — the same way the current single-master cluster starts.

**Why this priority**: Operational complexity kills HA setups. If the HA cluster requires 10 manual steps, it won't be used in practice.

**Independent Test**: Run `docker compose up` on a clean machine. Within 2 minutes, `http://localhost:8080` must show a Spark master UI with at least 2 workers registered — without any manual intervention.

**Acceptance Scenarios**:

1. **Given** a clean machine with Docker, **When** `docker compose up` runs, **Then** 3 master containers and N worker containers start, Zookeeper starts, and the active master is elected automatically
2. **Given** the cluster is running, **When** `docker compose down && docker compose up` is run, **Then** the cluster restarts to the same state without requiring manual master election

---

### Edge Cases

- What if all 3 masters fail simultaneously? → Cluster is unavailable — HA protects against single-master failure only; 3-master quorum requires at least 2 masters running
- What if Zookeeper is not available? → Masters cannot elect a leader; cluster goes into standby mode. Alert in logs.
- What if only 1 worker is available? → Jobs run with reduced parallelism; no HA impact on workers in this spec

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The cluster MUST run 3 Spark master containers managed by Zookeeper for leader election
- **FR-002**: Zookeeper MUST be added to the Docker Compose configuration as a separate service
- **FR-003**: The cluster MUST recover from a single master failure within 30 seconds (new master elected)
- **FR-004**: The `docker compose up` command MUST start the full HA cluster without manual intervention
- **FR-005**: Existing worker configuration MUST remain compatible (workers connect to any active master via Zookeeper URL)
- **FR-006**: The Spark master Web UI MUST remain accessible after a failover (served by the new active master)
- **FR-007**: The current `data/`, `src/`, `config.py` volume mounts MUST be preserved across all 3 master containers

### Key Entities

- **Zookeeper**: The coordination service responsible for Spark master leader election
- **Active Master**: The Spark master currently accepting job submissions (elected by Zookeeper)
- **Standby Master**: A Spark master that monitors the active master and takes over on failure
- **Quorum**: The minimum number of Zookeeper nodes required for a valid leader election (requires at least 2 of 3 masters)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Failover time from master failure to new master active is under 30 seconds
- **SC-002**: `docker compose up` starts the full HA cluster within 2 minutes from a cold start
- **SC-003**: All 3 masters show in Zookeeper's node list after startup
- **SC-004**: A job submitted after a master failover completes successfully

## Assumptions

- Current cluster has 1 master + N workers (docker-compose.yml)
- Zookeeper is not currently in the cluster — it must be added
- The project runs locally on a developer machine (Docker Desktop or Linux Docker)
- Production HA with 3 physical machines is out of scope — this is a local multi-container HA setup
- Existing notebooks do not need changes — they connect via `spark://` URL which supports Zookeeper HA mode
