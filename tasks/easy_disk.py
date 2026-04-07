"""
Task: Database Disk Full
WAL archiver falls behind on db-postgres, disk fills to 100%, database panics.
user-service and payment-service go down. Straightforward — the alert and logs
point directly at db-postgres.
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="easy_disk",
    name="Database Disk Full",
    difficulty="easy",
    max_steps=15,
    incident_summary=(
        "PagerDuty alert at 05:30 UTC. db-postgres is down — write errors detected, "
        "health check failing. user-service and payment-service both failing with database "
        "connection errors. api-gateway returning 503s on user and payment endpoints. "
        "Auth and notification paths are unaffected."
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
            status=ServiceStatus.DOWN, deps=["db-postgres"],
            version="v4.2.1", replicas=2,
        ),
        "payment-service": ServiceConfig(
            status=ServiceStatus.DOWN, deps=["db-postgres"],
            version="v3.8.1", replicas=2,
        ),
        "db-postgres": ServiceConfig(
            status=ServiceStatus.DOWN, deps=[],
            version="v15.4", replicas=1, is_root_cause=True, fault_type="disk_full",
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
        "[ALERT SEV-1] db-postgres: health check failing, write errors detected, disk space critical",
        "[ALERT SEV-2] user-service: elevated error rate, database connection failures",
        "[ALERT SEV-2] payment-service: transaction processing halted, database errors",
        "[ALERT SEV-3] api-gateway: 503 responses on /api/v2/user/* and /api/v2/pay endpoints",
    ],

    logs={
        "db-postgres": [
            "2026-04-06T05:00:00Z INFO  [db-postgres] Checkpoint starting: time-based",
            "2026-04-06T05:00:03Z INFO  [db-postgres] Checkpoint complete: wrote 2100 buffers (14.3%)",
            "2026-04-06T05:00:05Z INFO  [db-postgres] Active connections: 40/100",
            "2026-04-06T05:02:00Z INFO  [db-postgres] Autovacuum: processing table transactions (dead tuples: 8500)",
            "2026-04-06T05:05:00Z INFO  [db-postgres] Active connections: 42/100",
            "2026-04-06T05:08:00Z INFO  [db-postgres] WAL archiver: 12 segments pending archive",
            "2026-04-06T05:10:00Z WARN  [db-postgres] Disk usage: 82% on /var/lib/postgresql/data (48.4GB/59GB)",
            "2026-04-06T05:10:01Z WARN  [db-postgres] WAL archiver: 25 segments pending archive — archiver may be falling behind",
            "2026-04-06T05:12:00Z INFO  [db-postgres] Active connections: 44/100",
            "2026-04-06T05:15:00Z WARN  [db-postgres] WAL archiver: 45 segments pending archive — archive_command returning exit code 1",
            "2026-04-06T05:15:01Z WARN  [db-postgres] Disk usage: 87% on /var/lib/postgresql/data (51.3GB/59GB)",
            "2026-04-06T05:18:00Z WARN  [db-postgres] WAL archiver: 65 segments pending — archive_command failing consistently",
            "2026-04-06T05:20:00Z WARN  [db-postgres] Disk usage: 91% on /var/lib/postgresql/data (53.7GB/59GB)",
            "2026-04-06T05:20:01Z WARN  [db-postgres] Approaching critical disk threshold. Consider freeing space.",
            "2026-04-06T05:22:00Z WARN  [db-postgres] WAL archiver: 85 segments pending",
            "2026-04-06T05:25:00Z ERROR [db-postgres] Disk usage: 97% on /var/lib/postgresql/data (57.2GB/59GB) — critical threshold",
            "2026-04-06T05:25:01Z ERROR [db-postgres] WAL archiver: 120 segments pending — archive command failing with ENOSPC",
            "2026-04-06T05:26:00Z ERROR [db-postgres] INSERT on table orders failed: could not extend file — No space left on device",
            "2026-04-06T05:27:00Z ERROR [db-postgres] Suspending all write operations — insufficient disk space",
            "2026-04-06T05:28:00Z ERROR [db-postgres] Disk usage: 99% on /var/lib/postgresql/data (58.4GB/59GB)",
            "2026-04-06T05:29:00Z ERROR [db-postgres] Active transactions aborting due to write failures",
            "2026-04-06T05:30:00Z PANIC [db-postgres] could not write to file \"pg_wal/0000000100000042000000A8\": No space left on device",
            "2026-04-06T05:30:01Z ERROR [db-postgres] FATAL: WAL writer process crashed, terminating all connections",
            "2026-04-06T05:30:02Z ERROR [db-postgres] All active transactions aborted, database shutting down",
            "2026-04-06T05:30:03Z ERROR [db-postgres] Health check failed: connection refused on :5432",
        ],
        "user-service": [
            "2026-04-06T05:20:00Z INFO  [user-service] GET /users/profile uid=user_4421 -> 200 (32ms)",
            "2026-04-06T05:22:00Z INFO  [user-service] PUT /users/profile uid=user_3310 -> 200 (88ms)",
            "2026-04-06T05:25:00Z INFO  [user-service] GET /users/settings uid=user_8832 -> 200 (28ms)",
            "2026-04-06T05:26:00Z WARN  [user-service] Slow query: SELECT * FROM users WHERE id=... took 2800ms",
            "2026-04-06T05:27:00Z ERROR [user-service] Database write failed: INSERT INTO audit_log — No space left on device (via db-postgres)",
            "2026-04-06T05:28:00Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (35ms) — reads still working",
            "2026-04-06T05:30:01Z ERROR [user-service] Database connection failed: connection refused by db-postgres:5432",
            "2026-04-06T05:30:02Z ERROR [user-service] GET /users/profile uid=user_5571 -> 503 (database unavailable)",
            "2026-04-06T05:30:05Z ERROR [user-service] PUT /users/settings uid=user_7712 -> 503 (database unavailable)",
            "2026-04-06T05:30:10Z FATAL [user-service] No active database connections — all endpoints returning 503",
        ],
        "payment-service": [
            "2026-04-06T05:20:00Z INFO  [payment-service] Processing payment txn=pay_9910 amount=$35.00 -> db-postgres",
            "2026-04-06T05:20:01Z INFO  [payment-service] Payment completed txn=pay_9910 latency=88ms",
            "2026-04-06T05:25:00Z INFO  [payment-service] Processing payment txn=pay_1205 amount=$125.00 -> db-postgres",
            "2026-04-06T05:25:01Z INFO  [payment-service] Payment completed txn=pay_1205 latency=92ms",
            "2026-04-06T05:27:00Z ERROR [payment-service] Transaction failed: txn=pay_3378 — INSERT INTO transactions: No space left on device",
            "2026-04-06T05:28:00Z ERROR [payment-service] Transaction failed: txn=pay_4490 — database write error",
            "2026-04-06T05:30:01Z ERROR [payment-service] Database connection failed: connection refused by db-postgres:5432",
            "2026-04-06T05:30:02Z ERROR [payment-service] Transaction aborted: txn=pay_5501 — database unavailable",
            "2026-04-06T05:30:05Z ERROR [payment-service] All write operations halted — 0 active DB connections",
            "2026-04-06T05:30:10Z FATAL [payment-service] Transaction processing stopped — service DOWN",
        ],
        "api-gateway": [
            "2026-04-06T05:25:00Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms)",
            "2026-04-06T05:25:02Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 95ms)",
            "2026-04-06T05:25:05Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 42ms)",
            "2026-04-06T05:30:02Z ERROR [api-gateway] Route: GET /api/v2/user/profile -> user-service (503, 15ms)",
            "2026-04-06T05:30:03Z ERROR [api-gateway] Route: POST /api/v2/pay -> payment-service (503, 12ms)",
            "2026-04-06T05:30:05Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 42ms)",
            "2026-04-06T05:30:08Z INFO  [api-gateway] Route: GET /api/v2/notifications -> notification-service (200, 35ms)",
            "2026-04-06T05:30:10Z WARN  [api-gateway] 2/3 downstream services unhealthy (user-service, payment-service). Auth path operational.",
        ],
        "auth-service": [
            "2026-04-06T05:30:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8832 latency=42ms",
            "2026-04-06T05:30:05Z INFO  [auth-service] Cache hit for session sid=a8f32c, returning cached token",
            "2026-04-06T05:30:10Z INFO  [auth-service] Health check /healthz -> 200 OK",
        ],
        "cache-redis": [
            "2026-04-06T05:30:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T05:30:01Z INFO  [cache-redis] Cache hit ratio: 92%",
            "2026-04-06T05:30:05Z INFO  [cache-redis] Connected clients: 45",
        ],
        "notification-service": [
            "2026-04-06T05:30:00Z INFO  [notification-service] Email batch #5050 sent successfully (14 emails)",
            "2026-04-06T05:30:05Z INFO  [notification-service] Auth token validated for batch #5051 (42ms)",
            "2026-04-06T05:30:10Z INFO  [notification-service] Health check /healthz -> 200 OK",
        ],
    },

    metrics={
        "db-postgres": [
            {"timestamp": "2026-04-06T05:00:00Z", "cpu_pct": 30, "mem_pct": 55, "connections": 40, "disk_usage_pct": 78, "wal_segments_pending": 8, "write_iops": 1200, "read_iops": 3500},
            {"timestamp": "2026-04-06T05:10:00Z", "cpu_pct": 32, "mem_pct": 56, "connections": 42, "disk_usage_pct": 82, "wal_segments_pending": 25, "write_iops": 1100, "read_iops": 3400},
            {"timestamp": "2026-04-06T05:20:00Z", "cpu_pct": 35, "mem_pct": 57, "connections": 44, "disk_usage_pct": 91, "wal_segments_pending": 65, "write_iops": 600, "read_iops": 3200},
            {"timestamp": "2026-04-06T05:25:00Z", "cpu_pct": 38, "mem_pct": 58, "connections": 45, "disk_usage_pct": 97, "wal_segments_pending": 120, "write_iops": 100, "read_iops": 2800},
            {"timestamp": "2026-04-06T05:30:00Z", "cpu_pct": 0, "mem_pct": 0, "connections": 0, "disk_usage_pct": 100, "wal_segments_pending": 0, "write_iops": 0, "read_iops": 0},
        ],
        "user-service": [
            {"timestamp": "2026-04-06T05:25:00Z", "cpu_pct": 15, "mem_pct": 35, "latency_p50": 30, "latency_p99": 85, "error_rate": 0.001},
            {"timestamp": "2026-04-06T05:30:00Z", "cpu_pct": 5, "mem_pct": 32, "latency_p50": 0, "latency_p99": 0, "error_rate": 1.0},
        ],
        "payment-service": [
            {"timestamp": "2026-04-06T05:25:00Z", "cpu_pct": 18, "mem_pct": 40, "latency_p50": 88, "latency_p99": 155, "error_rate": 0.001},
            {"timestamp": "2026-04-06T05:30:00Z", "cpu_pct": 5, "mem_pct": 38, "latency_p50": 0, "latency_p99": 0, "error_rate": 1.0},
        ],
        "api-gateway": [
            {"timestamp": "2026-04-06T05:25:00Z", "cpu_pct": 20, "mem_pct": 45, "latency_p50": 35, "latency_p99": 90, "error_rate": 0.002, "5xx_rate": 0.001},
            {"timestamp": "2026-04-06T05:30:00Z", "cpu_pct": 18, "mem_pct": 44, "latency_p50": 38, "latency_p99": 95, "error_rate": 0.45, "5xx_rate": 0.42},
        ],
    },

    traces={
        "user-service": [
            "Trace: GET /api/v2/user/profile (uid=user_5571, total=15ms) — FAILED",
            "  ├─ user-service.lookupUser()         5ms",
            "  ├─ user-service.queryDB()             FAILED (db-postgres connection refused)",
            "  └─ user-service.returnError()          10ms  (503 database unavailable)",
        ],
        "payment-service": [
            "Trace: POST /api/v2/pay (txn=pay_5501, total=12ms) — FAILED",
            "  ├─ payment-service.validateRequest()   3ms",
            "  ├─ payment-service.insertTransaction()  FAILED (db-postgres connection refused)",
            "  └─ payment-service.returnError()         9ms  (503 database unavailable)",
        ],
    },

    deploy_history={
        "db-postgres": [
            "v15.4  deployed 2026-03-15T08:00:00Z  status=stable  (running 22 days, no issues until disk fill)",
        ],
        "user-service": [
            "v4.2.1  deployed 2026-04-05T16:00:00Z  status=stable  (running 13 hours)",
        ],
        "payment-service": [
            "v3.8.1  deployed 2026-04-03T14:00:00Z  status=stable  (running 3 days)",
        ],
    },

    runbooks={
        "db-postgres": (
            "## db-postgres Runbook\n"
            "- Disk full / No space left on device: WAL accumulation is the most common cause.\n"
            "  Check wal_segments_pending in metrics. Restart db-postgres to trigger WAL cleanup\n"
            "  and reclaim space. Then investigate why archiver fell behind (network to archive\n"
            "  storage, permissions, or archive_command misconfiguration).\n"
            "- Connection refused: Database may have crashed. Check logs for PANIC or FATAL.\n"
            "  Restart the service to recover.\n"
            "- High CPU: Check for expensive queries in pg_stat_statements."
        ),
        "user-service": (
            "## user-service Runbook\n"
            "- Database unavailable: Check db-postgres health first. user-service depends on\n"
            "  db-postgres for all read/write operations. If db-postgres is down, user-service\n"
            "  cannot recover until db-postgres is restored."
        ),
    },

    configs={
        "db-postgres": {
            "current": "max_connections=100\nshared_buffers=4GB\nwork_mem=256MB\nwal_level=replica\narchive_mode=on\narchive_command='test ! -f /archive/%f && cp %p /archive/%f'",
            "previous": "max_connections=100\nshared_buffers=4GB\nwork_mem=256MB\nwal_level=replica\narchive_mode=on\narchive_command='test ! -f /archive/%f && cp %p /archive/%f'",
            "diff": "No changes — config has not been modified recently. Disk filled due to WAL accumulation from archiver failure.",
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
    root_cause_categories=[RootCauseCategory.DISK_FULL],
    required_fixes=[
        RequiredFix(action="restart_service", service="db-postgres"),
    ],
    diagnosis_keywords=["db-postgres", "disk", "full", "space", "WAL", "write", "no space", "disk_full"],

    weights={
        "correct_service": 0.30,
        "correct_category": 0.20,
        "correct_fix": 0.30,
        "secondary_fix": 0.00,
        "diagnosis_text": 0.10,
        "investigation": 0.10,
        "wrong_penalty": 0.03,
    },
)
