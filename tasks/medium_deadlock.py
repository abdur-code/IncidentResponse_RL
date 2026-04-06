"""
Task: Cascading Database Deadlock
To add a new task, copy this file, modify the SCENARIO definition, and place it in tasks/.
The task loader will auto-discover it.
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="medium",
    name="Cascading Database Deadlock",
    difficulty="medium",
    max_steps=25,
    incident_summary=(
        "Multiple alerts fired at 03:05 UTC. payment-service and user-service both showing elevated "
        "error rates and latency. Transaction timeouts increasing. cache-redis also flagged with "
        "elevated miss ratio. Need to identify root cause and restore write path."
    ),

    services={
        "api-gateway": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service", "user-service", "payment-service"],
            version="v1.12.0", replicas=3,
        ),
        "auth-service": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=["cache-redis"],
            version="v2.14.0", replicas=2,
        ),
        "user-service": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["db-postgres"],
            version="v4.2.1", replicas=2,
        ),
        "payment-service": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["db-postgres"],
            version="v3.8.1", replicas=2,
        ),
        "db-postgres": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=[],
            version="v15.4", replicas=1, is_root_cause=True, fault_type="db_deadlock",
        ),
        "cache-redis": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=[],
            version="v7.2.4", replicas=1,
        ),
        "notification-service": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=["auth-service"],
            version="v1.5.0", replicas=1,
        ),
    },

    initial_alerts=[
        "[ALERT SEV-2] payment-service: transaction timeouts >15%, p99 latency >2s",
        "[ALERT SEV-2] user-service: elevated error rate on profile updates",
        "[ALERT SEV-3] cache-redis: cache miss ratio elevated (informational)",
    ],

    logs={
        "payment-service": [
            "2026-04-06T03:00:01Z INFO  [payment-service] Processing payment txn=pay_8832 amount=$45.00 -> db-postgres",
            "2026-04-06T03:00:02Z INFO  [payment-service] Payment completed txn=pay_8832 latency=85ms",
            "2026-04-06T03:00:10Z INFO  [payment-service] Processing payment txn=pay_1120 amount=$12.99 -> db-postgres",
            "2026-04-06T03:00:11Z INFO  [payment-service] Payment completed txn=pay_1120 latency=92ms",
            "2026-04-06T03:00:20Z INFO  [payment-service] Processing payment txn=pay_3341 amount=$199.00 -> db-postgres",
            "2026-04-06T03:00:21Z INFO  [payment-service] Payment completed txn=pay_3341 latency=78ms",
            "2026-04-06T03:01:00Z INFO  [payment-service] Health check /healthz -> 200 OK",
            "2026-04-06T03:02:00Z INFO  [payment-service] Processing payment txn=pay_5590 amount=$25.00 -> db-postgres",
            "2026-04-06T03:02:01Z INFO  [payment-service] Payment completed txn=pay_5590 latency=95ms",
            "2026-04-06T03:03:00Z INFO  [payment-service] Processing payment txn=pay_6612 amount=$150.00 -> db-postgres",
            "2026-04-06T03:03:01Z INFO  [payment-service] Payment completed txn=pay_6612 latency=88ms",
            "2026-04-06T03:04:00Z INFO  [payment-service] Health check /healthz -> 200 OK",
            "2026-04-06T03:05:00Z INFO  [payment-service] Processing payment txn=pay_7789 amount=$55.00 -> db-postgres",
            "2026-04-06T03:05:12Z WARN  [payment-service] Slow query: INSERT INTO transactions (...) took 3200ms (threshold: 500ms)",
            "2026-04-06T03:05:15Z INFO  [payment-service] Payment completed txn=pay_7789 latency=3250ms",
            "2026-04-06T03:05:16Z INFO  [payment-service] Processing payment txn=pay_1120 amount=$67.00 -> db-postgres",
            "2026-04-06T03:05:18Z WARN  [payment-service] DB connection pool: 48/50 active (96% utilized)",
            "2026-04-06T03:05:20Z ERROR [payment-service] Transaction timeout: txn=pay_4455 exceeded 5000ms deadline",
            "2026-04-06T03:05:20Z ERROR [payment-service] Retrying txn=pay_4455 (attempt 2/3)",
            "2026-04-06T03:05:25Z ERROR [payment-service] Transaction timeout: txn=pay_4455 exceeded 5000ms deadline (retry 2)",
            "2026-04-06T03:05:25Z ERROR [payment-service] Transaction failed permanently: txn=pay_4455 after 3 retries",
            "2026-04-06T03:05:26Z WARN  [payment-service] DB connection pool: 50/50 active (SATURATED) — new requests queuing",
            "2026-04-06T03:05:28Z ERROR [payment-service] Connection acquisition timeout: waited 10s for available connection",
            "2026-04-06T03:05:30Z INFO  [payment-service] Read query SELECT balance WHERE user_id=... completed in 45ms",
            "2026-04-06T03:05:32Z ERROR [payment-service] Transaction timeout: txn=pay_6691 exceeded 5000ms deadline",
            "2026-04-06T03:05:33Z WARN  [payment-service] Circuit breaker WARNING for db-postgres writes (failures=8/10 threshold)",
            "2026-04-06T03:05:35Z ERROR [payment-service] Transaction timeout: txn=pay_7801 exceeded 5000ms deadline",
            "2026-04-06T03:05:40Z ERROR [payment-service] Transaction timeout: txn=pay_8912 exceeded 5000ms deadline",
            "2026-04-06T03:06:00Z ERROR [payment-service] Connection acquisition timeout: waited 15s for available connection",
            "2026-04-06T03:07:00Z ERROR [payment-service] 12 transactions failed in last 5 minutes. Write path severely degraded.",
            "2026-04-06T03:08:00Z ERROR [payment-service] 15 transactions failed in last 5 minutes. Write path severely degraded.",
        ],
        "user-service": [
            "2026-04-06T03:00:01Z INFO  [user-service] GET /users/profile uid=user_4421 -> 200 (32ms)",
            "2026-04-06T03:00:05Z INFO  [user-service] GET /users/settings uid=user_8832 -> 200 (28ms)",
            "2026-04-06T03:00:10Z INFO  [user-service] PUT /users/profile uid=user_3310 -> 200 (85ms)",
            "2026-04-06T03:01:00Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (30ms)",
            "2026-04-06T03:02:00Z INFO  [user-service] PUT /users/settings uid=user_5571 -> 200 (78ms)",
            "2026-04-06T03:03:00Z INFO  [user-service] GET /users/profile uid=user_7712 -> 200 (27ms)",
            "2026-04-06T03:04:00Z INFO  [user-service] GET /users/profile uid=user_2209 -> 200 (31ms)",
            "2026-04-06T03:05:10Z INFO  [user-service] GET /users/profile uid=user_9901 -> 200 (29ms)",
            "2026-04-06T03:05:15Z INFO  [user-service] GET /users/profile uid=user_6633 -> 200 (26ms)",
            "2026-04-06T03:05:18Z WARN  [user-service] Slow mutation: UPDATE users SET email=... took 4100ms",
            "2026-04-06T03:05:20Z ERROR [user-service] Profile update failed: uid=user_8832 — database lock acquisition timeout",
            "2026-04-06T03:05:22Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (28ms)",
            "2026-04-06T03:05:25Z ERROR [user-service] Profile update failed: uid=user_3310 — database lock acquisition timeout",
            "2026-04-06T03:05:26Z WARN  [user-service] Write operations failing at 60% rate, reads unaffected",
            "2026-04-06T03:05:30Z INFO  [user-service] GET /users/profile uid=user_4482 -> 200 (30ms)",
            "2026-04-06T03:06:00Z ERROR [user-service] Profile update failed: uid=user_5510 — database lock acquisition timeout",
            "2026-04-06T03:06:05Z INFO  [user-service] GET /users/settings uid=user_7781 -> 200 (25ms)",
            "2026-04-06T03:07:00Z WARN  [user-service] Write operations failing at 75% rate, reads unaffected",
        ],
        "db-postgres": [
            "2026-04-06T02:55:00Z INFO  [db-postgres] Connection from analytics-cron@10.0.3.42: BEGIN; SELECT ... FROM transactions JOIN users ... (full table scan)",
            "2026-04-06T02:55:01Z INFO  [db-postgres] Query plan: Seq Scan on transactions (rows=2.4M, cost=45000..89000)",
            "2026-04-06T02:55:01Z WARN  [db-postgres] Long-running transaction txid=8830012 holding RowExclusiveLock on transactions table",
            "2026-04-06T02:56:00Z INFO  [db-postgres] Active connections: 55/100",
            "2026-04-06T02:58:00Z INFO  [db-postgres] Active connections: 68/100",
            "2026-04-06T03:00:00Z INFO  [db-postgres] Checkpoint starting: time-based",
            "2026-04-06T03:00:02Z INFO  [db-postgres] Checkpoint complete: wrote 1204 buffers (8.2%)",
            "2026-04-06T03:00:05Z INFO  [db-postgres] Active connections: 70/100",
            "2026-04-06T03:02:00Z INFO  [db-postgres] Active connections: 78/100",
            "2026-04-06T03:04:00Z INFO  [db-postgres] Active connections: 88/100",
            "2026-04-06T03:05:10Z WARN  [db-postgres] Deadlock detected: process 4821 (payment-service) waiting for RowExclusiveLock on transactions, blocked by process 4455 (analytics-cron)",
            "2026-04-06T03:05:10Z WARN  [db-postgres] Deadlock detected: process 4830 (user-service) waiting for RowExclusiveLock on users, blocked by process 4455 (analytics-cron)",
            "2026-04-06T03:05:11Z INFO  [db-postgres] Active connections: 95/100 (analytics-cron holding 1, payment-service pool 50, user-service pool 30, other 14)",
            "2026-04-06T03:05:15Z WARN  [db-postgres] Long-running transaction txid=8830012 has been active for 10m15s — consider terminating",
            "2026-04-06T03:05:20Z WARN  [db-postgres] Lock wait queue depth: 12 processes waiting",
            "2026-04-06T03:06:00Z INFO  [db-postgres] SELECT queries completing normally (read path unaffected)",
            "2026-04-06T03:06:30Z WARN  [db-postgres] Connection pool nearing limit: 98/100 active",
            "2026-04-06T03:07:00Z WARN  [db-postgres] Lock wait queue depth: 18 processes waiting — growing",
            "2026-04-06T03:08:00Z ERROR [db-postgres] Connection limit reached: 100/100 — rejecting new connections",
        ],
        "auth-service": [
            "2026-04-06T03:00:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8832 latency=42ms",
            "2026-04-06T03:00:05Z INFO  [auth-service] Cache hit for session sid=a8f32c, returning cached token",
            "2026-04-06T03:05:00Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_3310 latency=38ms",
            "2026-04-06T03:05:10Z INFO  [auth-service] Request processed: POST /auth/token uid=user_5571 latency=45ms",
            "2026-04-06T03:05:30Z INFO  [auth-service] Health check /healthz -> 200 OK",
            "2026-04-06T03:08:00Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_1101 latency=40ms",
        ],
        "cache-redis": [
            "2026-04-06T03:00:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T03:00:01Z INFO  [cache-redis] Cache hit ratio: 82% (normal: 85-95%)",
            "2026-04-06T03:02:00Z INFO  [cache-redis] Cache hit ratio: 80%",
            "2026-04-06T03:05:00Z INFO  [cache-redis] Cache hit ratio: 78% — slight decrease",
            "2026-04-06T03:05:01Z INFO  [cache-redis] Key evictions: 45 in last 5m (within normal range)",
            "2026-04-06T03:05:02Z WARN  [cache-redis] Cache miss ratio elevated for prefix auth:session:* — possible cache warming after TTL expiry batch",
            "2026-04-06T03:05:10Z INFO  [cache-redis] Memory usage: 1.3GB/4.0GB (32%) — stable",
            "2026-04-06T03:06:00Z INFO  [cache-redis] Cache hit ratio recovering: 84%",
            "2026-04-06T03:08:00Z INFO  [cache-redis] Cache hit ratio: 88% — back to normal",
        ],
        "api-gateway": [
            "2026-04-06T03:00:01Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 45ms)",
            "2026-04-06T03:00:02Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 88ms)",
            "2026-04-06T03:05:20Z WARN  [api-gateway] Route: POST /api/v2/pay -> payment-service (504, 5200ms)",
            "2026-04-06T03:05:22Z WARN  [api-gateway] Route: PUT /api/v2/user/profile -> user-service (504, 4800ms)",
            "2026-04-06T03:05:25Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms)",
            "2026-04-06T03:05:30Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 42ms)",
            "2026-04-06T03:06:00Z ERROR [api-gateway] Route: POST /api/v2/pay -> payment-service (504, timeout)",
        ],
        "notification-service": [
            "2026-04-06T03:00:00Z INFO  [notification-service] Email batch #4430 sent successfully (10 emails)",
            "2026-04-06T03:05:00Z INFO  [notification-service] Email batch #4435 sent successfully (7 emails)",
            "2026-04-06T03:08:00Z INFO  [notification-service] Health check /healthz -> 200 OK",
        ],
    },

    metrics={
        "payment-service": [
            {"timestamp": "2026-04-06T02:50:00Z", "cpu_pct": 20, "mem_pct": 40, "latency_p50": 80, "latency_p99": 150, "error_rate": 0.001, "db_pool_active": 15, "db_pool_max": 50},
            {"timestamp": "2026-04-06T03:00:00Z", "cpu_pct": 20, "mem_pct": 40, "latency_p50": 85, "latency_p99": 160, "error_rate": 0.002, "db_pool_active": 18, "db_pool_max": 50},
            {"timestamp": "2026-04-06T03:05:00Z", "cpu_pct": 22, "mem_pct": 41, "latency_p50": 3200, "latency_p99": 8500, "error_rate": 0.35, "db_pool_active": 50, "db_pool_max": 50},
            {"timestamp": "2026-04-06T03:08:00Z", "cpu_pct": 18, "mem_pct": 40, "latency_p50": 4500, "latency_p99": "timeout", "error_rate": 0.52, "db_pool_active": 50, "db_pool_max": 50},
        ],
        "user-service": [
            {"timestamp": "2026-04-06T02:50:00Z", "cpu_pct": 15, "mem_pct": 35, "latency_p50": 28, "latency_p99": 75, "error_rate": 0.001, "write_error_rate": 0.001},
            {"timestamp": "2026-04-06T03:05:00Z", "cpu_pct": 16, "mem_pct": 35, "latency_p50": 30, "latency_p99": 4100, "error_rate": 0.18, "write_error_rate": 0.60},
            {"timestamp": "2026-04-06T03:08:00Z", "cpu_pct": 15, "mem_pct": 35, "latency_p50": 28, "latency_p99": "timeout", "error_rate": 0.25, "write_error_rate": 0.75},
        ],
        "db-postgres": [
            {"timestamp": "2026-04-06T02:50:00Z", "cpu_pct": 35, "mem_pct": 60, "connections": 45, "active_locks": 3, "lock_wait_ms_p99": 5, "write_iops": 1200, "read_iops": 3500, "deadlocks": 0},
            {"timestamp": "2026-04-06T02:55:00Z", "cpu_pct": 55, "mem_pct": 62, "connections": 55, "active_locks": 8, "lock_wait_ms_p99": 15, "write_iops": 1200, "read_iops": 4200, "deadlocks": 0},
            {"timestamp": "2026-04-06T03:00:00Z", "cpu_pct": 65, "mem_pct": 64, "connections": 70, "active_locks": 15, "lock_wait_ms_p99": 250, "write_iops": 800, "read_iops": 4000, "deadlocks": 0},
            {"timestamp": "2026-04-06T03:05:00Z", "cpu_pct": 78, "mem_pct": 65, "connections": 95, "active_locks": 28, "lock_wait_ms_p99": 8500, "write_iops": 200, "read_iops": 3800, "deadlocks": 4},
            {"timestamp": "2026-04-06T03:08:00Z", "cpu_pct": 80, "mem_pct": 66, "connections": 100, "active_locks": 32, "lock_wait_ms_p99": 12000, "write_iops": 50, "read_iops": 3600, "deadlocks": 12},
        ],
        "auth-service": [
            {"timestamp": "2026-04-06T03:00:00Z", "cpu_pct": 22, "mem_pct": 58, "latency_p50": 42, "latency_p99": 110, "error_rate": 0.001},
            {"timestamp": "2026-04-06T03:08:00Z", "cpu_pct": 23, "mem_pct": 58, "latency_p50": 44, "latency_p99": 115, "error_rate": 0.001},
        ],
        "cache-redis": [
            {"timestamp": "2026-04-06T03:00:00Z", "mem_gb": 1.2, "mem_pct": 30, "hit_ratio": 0.82, "evictions_per_s": 8, "connections": 46},
            {"timestamp": "2026-04-06T03:05:00Z", "mem_gb": 1.3, "mem_pct": 32, "hit_ratio": 0.78, "evictions_per_s": 12, "connections": 46},
            {"timestamp": "2026-04-06T03:08:00Z", "mem_gb": 1.2, "mem_pct": 30, "hit_ratio": 0.88, "evictions_per_s": 2, "connections": 45},
        ],
        "api-gateway": [
            {"timestamp": "2026-04-06T03:00:00Z", "cpu_pct": 20, "mem_pct": 45, "latency_p50": 35, "latency_p99": 90, "error_rate": 0.002, "5xx_rate": 0.001},
            {"timestamp": "2026-04-06T03:05:00Z", "cpu_pct": 22, "mem_pct": 46, "latency_p50": 45, "latency_p99": 5500, "error_rate": 0.18, "5xx_rate": 0.15},
            {"timestamp": "2026-04-06T03:08:00Z", "cpu_pct": 23, "mem_pct": 46, "latency_p50": 50, "latency_p99": "timeout", "error_rate": 0.25, "5xx_rate": 0.22},
        ],
    },

    traces={
        "payment-service": [
            "Trace: POST /api/v2/pay (txn=pay_6691, total=8500ms) — TIMEOUT",
            "  ├─ payment-service.validateRequest()      12ms",
            "  ├─ payment-service.checkBalance()         45ms   (SELECT -> db-postgres, fast)",
            "  ├─ payment-service.insertTransaction()    8400ms (INSERT -> db-postgres, BLOCKED ON LOCK)",
            "  └─ payment-service.sendConfirmation()     never reached (timeout)",
        ],
        "user-service": [
            "Trace: PUT /api/v2/user/profile (uid=user_8832, total=4800ms) — TIMEOUT",
            "  ├─ user-service.validateInput()           5ms",
            "  ├─ user-service.updateProfile()           4780ms (UPDATE -> db-postgres, BLOCKED ON LOCK)",
            "  └─ user-service.invalidateCache()         never reached (timeout)",
        ],
    },

    deploy_history={
        "payment-service": [
            "v3.8.1  deployed 2026-04-03T14:00:00Z  status=stable  (running 3 days)",
        ],
        "user-service": [
            "v4.2.1  deployed 2026-04-05T16:00:00Z  status=stable  (running 11 hours)",
        ],
        "db-postgres": [
            "v15.4  deployed 2026-03-15T08:00:00Z  status=stable  (running 22 days)",
        ],
    },

    runbooks={
        "payment-service": (
            "## payment-service Runbook\n"
            "- Transaction timeouts: Check db-postgres connection pool and lock status.\n"
            "  If db connection pool is saturated but CPU/memory are normal, likely a DB-side issue.\n"
            "- High latency: Check downstream service health (db-postgres).\n"
            "- Crash on startup: Check recent deploys and rollback if needed."
        ),
        "db-postgres": (
            "## db-postgres Runbook\n"
            "- Deadlocks: Identify the blocking transaction using pg_stat_activity.\n"
            "  Kill long-running queries or restart postgres to clear all locks.\n"
            "- Connection exhaustion: Check for connection leaks. Consider increasing max_connections\n"
            "  or terminating idle connections.\n"
            "- High CPU: Check for expensive queries in pg_stat_statements. Consider adding indexes.\n"
            "- Replication lag: Check network connectivity to replicas and WAL sender status."
        ),
        "cache-redis": (
            "## cache-redis Runbook\n"
            "- Elevated miss ratio: Often caused by TTL expiry batches. Wait 5-10 minutes for cache\n"
            "  to warm back up. If miss ratio doesn't recover, check maxmemory and eviction policy.\n"
            "- Memory pressure: Check for memory leaks. Scale up replicas or increase maxmemory.\n"
            "- Connection issues: Check network connectivity and client pool configuration."
        ),
    },

    configs={
        "db-postgres": {
            "current": "max_connections=100\nshared_buffers=4GB\nwork_mem=256MB\nlock_timeout=30s\ndeadlock_timeout=1s",
            "previous": "max_connections=100\nshared_buffers=4GB\nwork_mem=256MB\nlock_timeout=30s\ndeadlock_timeout=1s",
            "diff": "No changes — config has not been modified recently.",
        },
        "payment-service": {
            "current": "DB_POOL_SIZE=50\nDB_TIMEOUT=5000\nRETRY_COUNT=3\nCIRCUIT_BREAKER_THRESHOLD=10",
            "previous": "DB_POOL_SIZE=50\nDB_TIMEOUT=5000\nRETRY_COUNT=3\nCIRCUIT_BREAKER_THRESHOLD=10",
            "diff": "No changes — config has not been modified recently.",
        },
    },

    dependencies={
        "api-gateway": ["auth-service", "user-service", "payment-service"],
        "auth-service": ["cache-redis"],
        "user-service": ["db-postgres"],
        "payment-service": ["db-postgres"],
        "db-postgres": [],
        "cache-redis": [],
        "notification-service": ["auth-service"],
    },

    root_cause_services=["db-postgres"],
    root_cause_categories=[RootCauseCategory.DB_DEADLOCK],
    required_fixes=[
        RequiredFix(action="restart_service", service="db-postgres"),
    ],
    diagnosis_keywords=["db-postgres", "deadlock", "lock", "analytics-cron", "long-running", "transaction", "blocking"],

    weights={
        "correct_service": 0.25,
        "correct_category": 0.20,
        "correct_fix": 0.25,
        "secondary_fix": 0.00,
        "diagnosis_text": 0.10,
        "investigation": 0.10,
        "wrong_penalty": 0.05,
    },
)

