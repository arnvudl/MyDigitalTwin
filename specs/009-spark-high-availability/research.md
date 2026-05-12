# Research: Spark High Availability

**Date**: 2026-05-12

## Decision 1: HA coordination service — Zookeeper vs. etcd vs. Kubernetes

**Decision**: Use Apache Zookeeper (single-node for local dev, 3-node for production).

**Rationale**: Spark's native HA support is built around Zookeeper. etcd would require a custom Spark build. Kubernetes is out of scope (the project uses Docker Compose). Zookeeper with `bitnami/zookeeper` Docker image is well-supported and well-documented with PySpark.

## Decision 2: Number of Spark masters

**Decision**: 3 master containers (1 active + 2 standby).

**Rationale**: 3 masters provide quorum tolerance — the cluster survives 1 master failure. 2 masters would mean a single standby with no quorum if the standby also fails. 3 is the standard minimum for Spark HA.

## Decision 3: Local vs. distributed Zookeeper

**Decision**: Single Zookeeper node for local development.

**Rationale**: A 3-node Zookeeper ensemble is for production HA of the coordination layer itself. For a local Docker Compose setup, a single Zookeeper node is sufficient — the goal is Spark master HA, not Zookeeper HA.

## Decision 4: Worker connection URL

**Decision**: Workers connect via `spark://spark-master-1:7077,spark-master-2:7077,spark-master-3:7077` (multi-master URL).

**Rationale**: Spark supports comma-separated master URLs for HA. Workers try each URL in order until they find an active master. Alternatively, use `spark://zk://zookeeper:2181/spark` — simpler but requires Spark 3.3+.

## Decision 5: Volume mounts

**Decision**: All 3 master containers share the same volume mounts as the current single master.

**Rationale**: The masters don't process data — they only coordinate jobs. Workers do the actual computation. Sharing volumes ensures all masters can serve the Spark UI with the same configuration.
