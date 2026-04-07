"""
Task: Config Error Masquerading as Database Problem
A configmap update pushed a wrong DB hostname to user-service. user-service can't
connect to db-postgres and goes down. db-postgres itself is fine — payment-service
still works perfectly.

Red herrings:
- db-postgres has "connection count dropped" alert (looks like DB issue)
- user-service logs show "host not found" (looks like DNS failure, but it's config error)
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="medium_config",
    name="Config Error with Misleading Database Symptoms",
    difficulty="medium",
    max_steps=25,
    incident_summary=(
        "Alert at 08:15 UTC. user-service is down with database connection failures. "
        "All user profile and settings endpoints returning 503s. payment-service "
        "(which also uses db-postgres) is operating normally. db-postgres flagged "
        "with an unusual connection drop. Need to identify root cause and restore "
        "user-service."
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
            version="v4.2.1", replicas=2, is_root_cause=True, fault_type="config_error",
        ),
        "payment-service": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=["db-postgres"],
            version="v3.8.1", replicas=2,
        ),
        "db-postgres": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=[],
            version="v15.4", replicas=1,
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
        "[ALERT SEV-1] user-service: 100% error rate on all endpoints, database connection failures",
        "[ALERT SEV-2] api-gateway: user profile and settings endpoints returning 503s",
        "[ALERT SEV-3] db-postgres: connection count dropped unexpectedly (informational)",
    ],

    logs={
        "user-service": [
            "2026-04-06T08:00:00Z INFO  [user-service] GET /users/profile uid=user_4421 -> 200 (32ms)",
            "2026-04-06T08:01:00Z INFO  [user-service] PUT /users/profile uid=user_3310 -> 200 (85ms)",
            "2026-04-06T08:02:00Z INFO  [user-service] GET /users/settings uid=user_8832 -> 200 (28ms)",
            "2026-04-06T08:03:00Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (30ms)",
            "2026-04-06T08:04:00Z INFO  [user-service] PUT /users/settings uid=user_5571 -> 200 (78ms)",
            "2026-04-06T08:05:00Z INFO  [user-service] Config reload triggered by configmap update",
            "2026-04-06T08:05:01Z INFO  [user-service] Applying new configuration: DB_HOST changed to db-postgres-primary.svc.cluster.local",
            "2026-04-06T08:05:02Z WARN  [user-service] Database connection pool reinitializing with new host...",
            "2026-04-06T08:05:03Z ERROR [user-service] Connection to database failed: getaddrinfo ENOTFOUND db-postgres-primary.svc.cluster.local",
            "2026-04-06T08:05:04Z ERROR [user-service] Retrying database connection (attempt 2/5)...",
            "2026-04-06T08:05:06Z ERROR [user-service] Connection to database failed: getaddrinfo ENOTFOUND db-postgres-primary.svc.cluster.local (attempt 2)",
            "2026-04-06T08:05:08Z ERROR [user-service] Retrying database connection (attempt 3/5)...",
            "2026-04-06T08:05:10Z ERROR [user-service] Connection to database failed: getaddrinfo ENOTFOUND db-postgres-primary.svc.cluster.local (attempt 3)",
            "2026-04-06T08:05:12Z ERROR [user-service] Retrying database connection (attempt 4/5)...",
            "2026-04-06T08:05:14Z ERROR [user-service] Connection to database failed: getaddrinfo ENOTFOUND db-postgres-primary.svc.cluster.local (attempt 4)",
            "2026-04-06T08:05:16Z ERROR [user-service] Retrying database connection (attempt 5/5)...",
            "2026-04-06T08:05:18Z ERROR [user-service] Connection to database failed: getaddrinfo ENOTFOUND db-postgres-primary.svc.cluster.local (attempt 5)",
            "2026-04-06T08:05:19Z ERROR [user-service] All 5 database connection attempts failed — marking service unhealthy",
            "2026-04-06T08:05:20Z ERROR [user-service] GET /users/profile uid=user_7712 -> 503 (database unavailable)",
            "2026-04-06T08:05:22Z ERROR [user-service] PUT /users/settings uid=user_2209 -> 503 (database unavailable)",
            "2026-04-06T08:05:25Z FATAL [user-service] No active database connections — all endpoints returning 503",
            "2026-04-06T08:05:30Z INFO  [user-service] Note: configmap was corrected at 08:10 but service needs restart to pick up the fix",
        ],
        "db-postgres": [
            "2026-04-06T08:00:00Z INFO  [db-postgres] Active connections: 65/100 (user-service: 30, payment-service: 25, other: 10)",
            "2026-04-06T08:02:00Z INFO  [db-postgres] Checkpoint starting: time-based",
            "2026-04-06T08:02:02Z INFO  [db-postgres] Checkpoint complete: wrote 920 buffers (6.3%)",
            "2026-04-06T08:04:00Z INFO  [db-postgres] Active connections: 66/100",
            "2026-04-06T08:05:00Z INFO  [db-postgres] Active connections: 35/100 (user-service: 0, payment-service: 25, other: 10)",
            "2026-04-06T08:05:01Z INFO  [db-postgres] Notice: user-service connection pool closed — 30 connections released simultaneously",
            "2026-04-06T08:05:05Z INFO  [db-postgres] All remaining queries executing normally. No lock contention detected.",
            "2026-04-06T08:05:10Z INFO  [db-postgres] Active connections: 35/100 — stable at reduced level",
            "2026-04-06T08:06:00Z INFO  [db-postgres] Autovacuum: processing table users (dead tuples: 150)",
            "2026-04-06T08:08:00Z INFO  [db-postgres] Active connections: 36/100 — no reconnection from user-service",
            "2026-04-06T08:10:00Z INFO  [db-postgres] Active connections: 35/100. Database operating normally.",
        ],
        "payment-service": [
            "2026-04-06T08:00:00Z INFO  [payment-service] Processing payment txn=pay_2210 amount=$45.00 -> db-postgres",
            "2026-04-06T08:00:01Z INFO  [payment-service] Payment completed txn=pay_2210 latency=85ms",
            "2026-04-06T08:05:00Z INFO  [payment-service] Processing payment txn=pay_3341 amount=$22.99 -> db-postgres",
            "2026-04-06T08:05:01Z INFO  [payment-service] Payment completed txn=pay_3341 latency=92ms",
            "2026-04-06T08:10:00Z INFO  [payment-service] Processing payment txn=pay_4452 amount=$150.00 -> db-postgres",
            "2026-04-06T08:10:01Z INFO  [payment-service] Payment completed txn=pay_4452 latency=88ms",
            "2026-04-06T08:10:05Z INFO  [payment-service] Health check /healthz -> 200 OK",
        ],
        "api-gateway": [
            "2026-04-06T08:04:00Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms)",
            "2026-04-06T08:05:02Z ERROR [api-gateway] Route: GET /api/v2/user/profile -> user-service (503, 18ms)",
            "2026-04-06T08:05:05Z ERROR [api-gateway] Route: PUT /api/v2/user/settings -> user-service (503, 15ms)",
            "2026-04-06T08:05:08Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 88ms)",
            "2026-04-06T08:05:10Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 42ms)",
            "2026-04-06T08:05:12Z ERROR [api-gateway] Route: GET /api/v2/user/profile -> user-service (503, 12ms)",
            "2026-04-06T08:08:00Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 90ms)",
            "2026-04-06T08:10:00Z ERROR [api-gateway] Route: PUT /api/v2/user/settings -> user-service (503, 14ms)",
            "2026-04-06T08:10:02Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 40ms)",
        ],
        "auth-service": [
            "2026-04-06T08:05:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8832 latency=42ms",
            "2026-04-06T08:05:05Z INFO  [auth-service] Cache hit for session sid=a8f32c, returning cached token",
            "2026-04-06T08:10:00Z INFO  [auth-service] Health check /healthz -> 200 OK",
        ],
        "cache-redis": [
            "2026-04-06T08:05:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T08:05:01Z INFO  [cache-redis] Cache hit ratio: 92%",
            "2026-04-06T08:10:00Z INFO  [cache-redis] Connected clients: 44",
        ],
        "notification-service": [
            "2026-04-06T08:05:00Z INFO  [notification-service] Email batch #5150 sent successfully (10 emails)",
            "2026-04-06T08:10:00Z INFO  [notification-service] Health check /healthz -> 200 OK",
        ],
    },

    metrics={
        "user-service": [
            {"timestamp": "2026-04-06T08:00:00Z", "cpu_pct": 15, "mem_pct": 35, "latency_p50": 28, "latency_p99": 85, "error_rate": 0.001, "db_connections": 30},
            {"timestamp": "2026-04-06T08:05:00Z", "cpu_pct": 5, "mem_pct": 32, "latency_p50": 0, "latency_p99": 0, "error_rate": 1.0, "db_connections": 0},
        ],
        "db-postgres": [
            {"timestamp": "2026-04-06T08:00:00Z", "cpu_pct": 30, "mem_pct": 55, "connections": 65, "deadlocks": 0, "write_iops": 1200, "read_iops": 3500},
            {"timestamp": "2026-04-06T08:05:00Z", "cpu_pct": 22, "mem_pct": 54, "connections": 35, "deadlocks": 0, "write_iops": 1100, "read_iops": 3200},
            {"timestamp": "2026-04-06T08:10:00Z", "cpu_pct": 20, "mem_pct": 54, "connections": 35, "deadlocks": 0, "write_iops": 1100, "read_iops": 3100},
        ],
        "payment-service": [
            {"timestamp": "2026-04-06T08:00:00Z", "cpu_pct": 18, "mem_pct": 40, "latency_p50": 85, "latency_p99": 150, "error_rate": 0.001},
            {"timestamp": "2026-04-06T08:10:00Z", "cpu_pct": 18, "mem_pct": 40, "latency_p50": 88, "latency_p99": 155, "error_rate": 0.001},
        ],
    },

    traces={
        "user-service": [
            "Trace: GET /api/v2/user/profile (uid=user_7712, total=18ms) — FAILED",
            "  ├─ user-service.parseRequest()            2ms",
            "  ├─ user-service.connectDB()               FAILED (getaddrinfo ENOTFOUND db-postgres-primary.svc.cluster.local)",
            "  └─ user-service.returnError()              16ms  (503 database unavailable)",
        ],
    },

    deploy_history={
        "user-service": [
            "v4.2.1  deployed 2026-04-05T16:00:00Z  status=stable  (running 16 hours until config break)",
            "v4.2.0  deployed 2026-04-01T11:00:00Z  status=superseded",
        ],
        "db-postgres": [
            "v15.4  deployed 2026-03-15T08:00:00Z  status=stable  (running 22 days)",
        ],
    },

    runbooks={
        "user-service": (
            "## user-service Runbook\n"
            "- Database connection failures: First check if db-postgres is healthy.\n"
            "  If db-postgres is up and payment-service works, the issue is likely in\n"
            "  user-service's connection configuration (DB_HOST, credentials, network).\n"
            "  Check diff_config for recent changes. If config was corrected in the\n"
            "  configmap but service hasn't picked it up, restart the service.\n"
            "- 'Host not found' errors: Could be DNS failure OR wrong hostname in config.\n"
            "  Use diff_config to check if DB_HOST was recently changed."
        ),
        "db-postgres": (
            "## db-postgres Runbook\n"
            "- Connection count drop: If connections drop suddenly from one client (e.g.,\n"
            "  user-service pool closing), investigate the client service, not db-postgres.\n"
            "  The database is likely fine — it just lost clients.\n"
            "- Deadlocks: Check pg_stat_activity for blocking queries."
        ),
    },

    configs={
        "user-service": {
            "current": "DB_HOST=db-postgres-primary.svc.cluster.local\nDB_PORT=5432\nDB_NAME=userdb\nDB_POOL_SIZE=30\nDB_TIMEOUT=5000",
            "previous": "DB_HOST=db-postgres.svc.cluster.local\nDB_PORT=5432\nDB_NAME=userdb\nDB_POOL_SIZE=30\nDB_TIMEOUT=5000",
            "diff": "DB_HOST changed from 'db-postgres.svc.cluster.local' to 'db-postgres-primary.svc.cluster.local'. This hostname does not exist — there is no primary/replica split in this cluster. The configmap has since been corrected, but the running service still has the wrong hostname loaded. A restart will pick up the corrected config.",
        },
        "db-postgres": {
            "current": "max_connections=100\nshared_buffers=4GB\nwork_mem=256MB",
            "previous": "max_connections=100\nshared_buffers=4GB\nwork_mem=256MB",
            "diff": "No changes — db-postgres config has not been modified.",
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

    root_cause_services=["user-service"],
    root_cause_categories=[RootCauseCategory.CONFIG_ERROR],
    required_fixes=[
        RequiredFix(action="restart_service", service="user-service"),
    ],
    diagnosis_keywords=["user-service", "config", "configuration", "DB_HOST", "hostname", "wrong", "typo", "config_error", "configmap", "connection string"],

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
