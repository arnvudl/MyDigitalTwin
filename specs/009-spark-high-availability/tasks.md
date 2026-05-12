# Tasks: Spark High Availability

**Input**: Design documents from `specs/009-spark-high-availability/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

---

## Phase 1: Zookeeper Service

- [ ] T001 Add `zookeeper` service to `docker-compose.yml` using `bitnami/zookeeper:3.9` image with `ALLOW_ANONYMOUS_LOGIN=yes`, port 2181, and healthcheck

**Checkpoint**: `docker compose up zookeeper` starts cleanly, port 2181 reachable ✅

---

## Phase 2: 3 Spark Master Services

- [ ] T002 Rename existing `spark-master` service to `spark-master-1` in `docker-compose.yml` (adjust container_name, ports remain 8080/7077)
- [ ] T003 Add `spark-master-2` service cloned from `spark-master-1` with ports 8081 (UI) and 7078 (Spark); add `depends_on: zookeeper`
- [ ] T004 Add `spark-master-3` service cloned from `spark-master-1` with ports 8082 (UI) and 7079 (Spark); add `depends_on: zookeeper`
- [ ] T005 Add HA environment variables to all 3 master services in `.env.spark` (or inline in docker-compose): `SPARK_MASTER_RECOVERY_MODE=ZOOKEEPER`, `SPARK_MASTER_RECOVERY_DIRECTORY=zookeeper:2181/spark`
- [ ] T006 Update `entrypoint.sh` to pass `--conf spark.deploy.recoveryMode=ZOOKEEPER --conf spark.deploy.zookeeper.url=zookeeper:2181` when starting in `master` mode

**Checkpoint**: `docker compose up spark-master-1 spark-master-2 spark-master-3` — all 3 masters start, one becomes active, logs show "I have been elected leader" ✅

---

## Phase 3: Worker & Client Configuration

- [ ] T007 Update worker `SPARK_MASTER` environment variable to multi-master URL: `spark://spark-master-1:7077,spark-master-2:7077,spark-master-3:7077`
- [ ] T008 Update `config.py` `build_spark_session()` master URL to same multi-master URL (or Zookeeper URL if Spark 3.3+ is confirmed)

**Checkpoint**: `docker compose up` → workers register with the active master shown in Spark UI ✅

---

## Phase 4: Failover Validation

- [ ] T009 Start full cluster: `docker compose up -d`
- [ ] T010 Identify the active master by checking logs: `docker compose logs spark-master-1 | grep -i "leader"`
- [ ] T011 Stop the active master: `docker stop <active-master-container>`
- [ ] T012 Wait 30 seconds and verify a new master is elected in the remaining master logs
- [ ] T013 Submit a smoke test job to the cluster after failover and confirm it completes

**Checkpoint**: Failover under 30s, smoke test passes after failover ✅

---

## Dependencies & Execution Order

```
T001 (Zookeeper) → T002–T006 (3 masters) → T007–T008 (workers + config) → T009–T013 (validation)
```

T002–T005 can be done in parallel (editing different services in docker-compose.yml).

---

## Summary

| Phase | Scope | Tasks | Gate |
|-------|-------|-------|------|
| 1 — Zookeeper | docker-compose.yml | T001 | Port 2181 healthy |
| 2 — Masters | docker-compose.yml, entrypoint | T002–T006 | 3 masters up, 1 elected |
| 3 — Workers | docker-compose.yml, config.py | T007–T008 | Workers connect to active master |
| 4 — Validation | Manual test | T009–T013 | Failover < 30s, job passes |

**Total**: 13 tasks | **MVP scope**: T001–T008 (cluster up, no failover test)
