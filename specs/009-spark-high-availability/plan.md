# Implementation Plan: Spark High Availability

**Branch**: `docs/architecture-specs` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)

---

## Summary

Extend `docker-compose.yml` to add Zookeeper and 2 additional Spark master containers. Update `entrypoint.sh` or Spark configuration to enable Zookeeper-based HA mode. Workers connect via multi-master URL. The existing single-master setup becomes `spark-master-1`.

---

## Technical Context

**Coordination**: Zookeeper (single node, `bitnami/zookeeper` image)  
**Masters**: 3 containers (`spark-master-1`, `spark-master-2`, `spark-master-3`)  
**Workers**: unchanged  
**Spark HA config**: `spark.deploy.recoveryMode=ZOOKEEPER` + `spark.deploy.zookeeper.url=zookeeper:2181`  
**Scope**: `docker-compose.yml`, `entrypoint.sh` (or `spark-defaults.conf`)

---

## Constitution Check

- [x] No hardcoded paths — volume mounts reference relative `./` paths (unchanged)
- [x] No code changes to parsers or notebooks
- [x] `data/` directory mounts preserved on all masters
- [x] Existing `OVERWRITE` patterns and MERGE INTO unaffected

**No constitution violations.**

---

## Project Structure

```text
docker-compose.yml          ← add zookeeper, spark-master-2, spark-master-3 services
.env.spark                  ← add SPARK_MASTER_RECOVERY_MODE=ZOOKEEPER
                               add SPARK_MASTER_RECOVERY_DIRECTORY=zookeeper:2181/spark
entrypoint.sh               ← pass recovery env vars to spark-class when mode=master
```

---

## Implementation Phases

### Phase 1: Zookeeper Service

**Output**: Zookeeper container in `docker-compose.yml`  
**Dependencies**: None

```yaml
zookeeper:
  image: bitnami/zookeeper:3.9
  container_name: zookeeper
  environment:
    - ALLOW_ANONYMOUS_LOGIN=yes
  ports:
    - "2181:2181"
  healthcheck:
    test: ["CMD", "zkServer.sh", "status"]
    interval: 10s
    timeout: 5s
    retries: 3
```

---

### Phase 2: 3 Spark Master Services

**Output**: `spark-master-1`, `spark-master-2`, `spark-master-3` in `docker-compose.yml`  
**Dependencies**: Phase 1 (Zookeeper must be healthy before masters start)

Rename existing `spark-master` → `spark-master-1`. Clone to `spark-master-2` and `spark-master-3` with adjusted port mappings (8081/8082 for UI, 7078/7079 for Spark).

Add HA environment variables to each master:
```yaml
environment:
  - SPARK_MASTER_RECOVERY_MODE=ZOOKEEPER
  - SPARK_MASTER_RECOVERY_DIRECTORY=zookeeper:2181/spark
```

---

### Phase 3: Worker & Client Configuration

**Output**: Workers connect via multi-master URL  
**Dependencies**: Phase 2

Update worker `SPARK_MASTER_URL` to:
```
spark://spark-master-1:7077,spark-master-2:7077,spark-master-3:7077
```

Update notebooks' `spark://` URL in `config.py` `build_spark_session()` — or rely on Zookeeper discovery URL `spark://zk://zookeeper:2181/spark` if Spark version supports it.

---

### Phase 4: Failover Validation

**Output**: Verified HA behavior  
**Dependencies**: Phase 1–3

1. `docker compose up -d`
2. Identify active master: `docker compose logs spark-master-1 | grep "I have been elected"` (or equivalent)
3. Stop active master: `docker stop spark-master-1`
4. Wait 30s, verify new active master in logs
5. Submit test job: `spark-submit --master spark://spark-master-2:7077,... tests/spark_smoke_test.py`

---

## Architecture Decisions

- **Single Zookeeper node**: Sufficient for local dev — goal is Spark HA, not Zookeeper HA
- **bitnami/zookeeper image**: Well-maintained, minimal configuration required
- **3 masters (not 2)**: Quorum tolerance — cluster survives 1 failure; 2 masters offer no quorum safety
- **Port offset per master**: UI ports 8080/8081/8082, Spark ports 7077/7078/7079 to avoid conflicts on the host
