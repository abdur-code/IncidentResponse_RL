"""
Task: Database Disk Full + Auth Certificate Expiry (Concurrent Faults)

Two independent faults on separate dependency paths:
1. db-postgres: WAL accumulation fills disk, database crashes.
   user-service and payment-service go DOWN.
2. auth-service: internal mTLS certificate expired. 30% of requests fail
   (new TLS connections fail, cached sessions still work).

Red herrings:
- db-postgres crash is loud and dominates attention (anchoring bias)
- After fixing db-postgres, agent may think everything is resolved
- auth-service is on a SEPARATE dependency path (auth→cache-redis, NOT auth→db-postgres)
- cache-redis hit ratio dips slightly (benign — auth not writing back on failed mTLS)
- notification-service failures could be attributed to "general instability"
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="hard_disk_cert",
    name="Database Disk Exhaustion with Auth Certificate Failure",
    difficulty="hard",
    max_steps=35,
    incident_summary=(
        "SEV-1 declared at 10:00 UTC. Major multi-service outage. db-postgres is "
        "completely down, taking user-service and payment-service with it. Simultaneously, "
        "auth-service is experiencing intermittent failures unrelated to the database "
        "outage — token validation is failing with TLS errors for approximately 30% of "
        "requests. api-gateway affected by both failure paths. notification-service "
        "partially impaired. This appears to be a compound incident with multiple root "
        "causes."
    ),

    services={
        "api-gateway": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service", "user-service", "payment-service"],
            version="v1.12.0", replicas=3,
        ),
        "auth-service": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["cache-redis"],
            version="v2.14.0", replicas=2, is_root_cause=True, fault_type="cert_expiry",
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
            status=ServiceStatus.DEGRADED, deps=["auth-service"],
            version="v1.5.0", replicas=1,
        ),
    },

    initial_alerts=[
        "[ALERT SEV-1] db-postgres: service DOWN, all connections terminated, disk space critical",
        "[ALERT SEV-1] user-service: database unavailable, all endpoints failing",
        "[ALERT SEV-1] payment-service: database unavailable, transaction processing halted",
        "[ALERT SEV-2] auth-service: intermittent mTLS handshake failures, 30% error rate",
        "[ALERT SEV-2] notification-service: auth validation intermittently failing, queue growing",
        "[ALERT SEV-2] api-gateway: error rate >50% across multiple endpoints",
    ],

    logs={
        "db-postgres": [
            "2026-04-06T09:30:00Z INFO  [db-postgres] Active connections: 68/100",
            "2026-04-06T09:35:00Z INFO  [db-postgres] Checkpoint starting: time-based",
            "2026-04-06T09:35:02Z INFO  [db-postgres] Checkpoint complete: wrote 1800 buffers (12.2%)",
            "2026-04-06T09:40:00Z WARN  [db-postgres] Disk usage: 88% on /var/lib/postgresql/data (51.9GB/59GB)",
            "2026-04-06T09:40:01Z WARN  [db-postgres] WAL archiver: 50 segments pending archive",
            "2026-04-06T09:45:00Z WARN  [db-postgres] WAL archiver: 80 segments pending archive — archiver falling behind",
            "2026-04-06T09:45:01Z WARN  [db-postgres] Disk usage: 91% on /var/lib/postgresql/data (53.7GB/59GB)",
            "2026-04-06T09:48:00Z ERROR [db-postgres] Disk usage: 94% — archive_command failing with ENOSPC on target",
            "2026-04-06T09:50:00Z ERROR [db-postgres] Disk usage: 95% on /var/lib/postgresql/data (56.1GB/59GB)",
            "2026-04-06T09:50:01Z ERROR [db-postgres] WAL archiver: 150 segments pending — archive command failing with ENOSPC",
            "2026-04-06T09:52:00Z ERROR [db-postgres] INSERT on table audit_log failed: could not extend file — No space left on device",
            "2026-04-06T09:55:00Z ERROR [db-postgres] Disk usage: 98% — suspending non-critical writes",
            "2026-04-06T09:58:00Z ERROR [db-postgres] Disk usage: 99% — emergency: all write paths blocked",
            "2026-04-06T10:00:00Z PANIC [db-postgres] could not write to file \"pg_wal/0000000100000045000000B2\": No space left on device",
            "2026-04-06T10:00:01Z ERROR [db-postgres] FATAL: WAL writer process crashed, terminating all connections",
            "2026-04-06T10:00:02Z ERROR [db-postgres] All active transactions aborted, database shutting down",
            "2026-04-06T10:00:03Z ERROR [db-postgres] Health check failed: connection refused on :5432",
        ],
        "auth-service": [
            "2026-04-06T09:50:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8832 -> cache HIT (12ms)",
            "2026-04-06T09:52:00Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_4421 -> cache HIT (11ms)",
            "2026-04-06T09:55:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_3310 -> cache HIT (14ms)",
            "2026-04-06T09:58:00Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_5571 latency=12ms",
            "2026-04-06T09:59:59Z WARN  [auth-service] Internal mTLS certificate for inter-service auth expires in 1 second",
            "2026-04-06T09:59:59Z WARN  [auth-service] cert-manager renewal pending — certificate will auto-renew in secret",
            "2026-04-06T10:00:00Z ERROR [auth-service] mTLS handshake failed for incoming request: certificate has expired (not after: 2026-04-06T09:59:59Z)",
            "2026-04-06T10:00:01Z INFO  [auth-service] Request via cached TLS session: POST /auth/token uid=user_7712 -> 200 (14ms)",
            "2026-04-06T10:00:02Z ERROR [auth-service] mTLS handshake failed for incoming request from api-gateway: x509: certificate has expired",
            "2026-04-06T10:00:03Z INFO  [auth-service] Request via cached TLS session: POST /auth/verify uid=user_2209 -> 200 (18ms)",
            "2026-04-06T10:00:04Z ERROR [auth-service] mTLS handshake failed for incoming request from notification-service: x509: certificate has expired",
            "2026-04-06T10:00:05Z WARN  [auth-service] 30% of incoming requests failing mTLS validation — new connections affected, cached sessions OK",
            "2026-04-06T10:00:06Z INFO  [auth-service] Internal subsystems healthy: cache-redis responding, token validation logic OK",
            "2026-04-06T10:00:08Z INFO  [auth-service] cert-manager renewed certificate in secret auth-service-mtls at 09:58:00Z — process restart required to reload",
            "2026-04-06T10:00:10Z ERROR [auth-service] mTLS handshake failed for incoming request from api-gateway: x509: certificate has expired",
            "2026-04-06T10:00:12Z INFO  [auth-service] Request via cached TLS session: POST /auth/token uid=user_1101 -> 200 (13ms)",
            "2026-04-06T10:00:15Z WARN  [auth-service] Error rate: 30% — only new TLS connections affected, cached sessions continue working",
        ],
        "user-service": [
            "2026-04-06T09:55:00Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (30ms)",
            "2026-04-06T09:58:00Z INFO  [user-service] PUT /users/settings uid=user_3310 -> 200 (82ms)",
            "2026-04-06T10:00:01Z ERROR [user-service] Database connection failed: connection refused by db-postgres:5432",
            "2026-04-06T10:00:02Z ERROR [user-service] All endpoints returning 503 — database unavailable",
            "2026-04-06T10:00:05Z ERROR [user-service] GET /users/profile uid=user_5571 -> 503",
            "2026-04-06T10:00:10Z FATAL [user-service] No database connections available — service DOWN",
        ],
        "payment-service": [
            "2026-04-06T09:55:00Z INFO  [payment-service] Payment completed txn=pay_8801 latency=85ms",
            "2026-04-06T09:58:00Z INFO  [payment-service] Payment completed txn=pay_9920 latency=92ms",
            "2026-04-06T10:00:01Z ERROR [payment-service] Database connection failed: connection refused by db-postgres:5432",
            "2026-04-06T10:00:02Z ERROR [payment-service] Transaction aborted: txn=pay_1035 — database unavailable",
            "2026-04-06T10:00:05Z ERROR [payment-service] All write operations halted — 0 active DB connections",
            "2026-04-06T10:00:10Z FATAL [payment-service] Transaction processing halted — service DOWN",
        ],
        "notification-service": [
            "2026-04-06T09:55:00Z INFO  [notification-service] Email batch #5300 sent successfully (14 emails)",
            "2026-04-06T09:58:00Z INFO  [notification-service] Auth validation for batch #5305: 42ms (cached TLS session)",
            "2026-04-06T10:00:00Z INFO  [notification-service] Auth validation for batch #5308: succeeded (cached TLS session, 45ms)",
            "2026-04-06T10:00:03Z ERROR [notification-service] Auth validation for batch #5309: TLS handshake failed with auth-service — x509: certificate expired",
            "2026-04-06T10:00:05Z INFO  [notification-service] Auth validation for batch #5310: succeeded (cached TLS session, 48ms)",
            "2026-04-06T10:00:08Z WARN  [notification-service] Auth validation intermittently failing — ~30% failure rate on new TLS connections",
            "2026-04-06T10:00:10Z ERROR [notification-service] Auth validation for batch #5311: TLS handshake failed",
            "2026-04-06T10:00:12Z INFO  [notification-service] Auth validation for batch #5312: succeeded (cached session)",
            "2026-04-06T10:00:15Z WARN  [notification-service] Queue depth: 1200 — delivery slowing due to auth validation retries",
        ],
        "api-gateway": [
            "2026-04-06T09:58:00Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 14ms)",
            "2026-04-06T09:58:02Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms)",
            "2026-04-06T10:00:01Z ERROR [api-gateway] Route: GET /api/v2/user/profile -> user-service (503, connection refused)",
            "2026-04-06T10:00:02Z ERROR [api-gateway] Route: POST /api/v2/pay -> payment-service (503, connection refused)",
            "2026-04-06T10:00:03Z ERROR [api-gateway] Route: POST /api/v2/login -> auth-service (502, TLS handshake failed: x509 cert expired)",
            "2026-04-06T10:00:05Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 14ms) — via cached TLS session",
            "2026-04-06T10:00:06Z INFO  [api-gateway] Route: GET /api/v2/user/settings -> user-service (503, connection refused)",
            "2026-04-06T10:00:08Z ERROR [api-gateway] Route: POST /api/v2/verify -> auth-service (502, TLS handshake failed)",
            "2026-04-06T10:00:10Z WARN  [api-gateway] Error rate: 55% — user/payment DOWN, auth intermittent",
            "2026-04-06T10:00:12Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 13ms) — cached TLS",
            "2026-04-06T10:00:15Z ERROR [api-gateway] Route: POST /api/v2/pay -> payment-service (503, connection refused)",
        ],
        "cache-redis": [
            "2026-04-06T10:00:00Z INFO  [cache-redis] Memory usage: 1.3GB/4.0GB (32%)",
            "2026-04-06T10:00:01Z INFO  [cache-redis] Cache hit ratio: 88% (slight dip — auth-service not writing back on some requests)",
            "2026-04-06T10:00:05Z INFO  [cache-redis] Connected clients: 38 (down from 45 — some auth-service connections failed on mTLS)",
            "2026-04-06T10:00:10Z INFO  [cache-redis] Key evictions: 0 — memory stable, no pressure",
        ],
    },

    metrics={
        "db-postgres": [
            {"timestamp": "2026-04-06T09:30:00Z", "cpu_pct": 35, "mem_pct": 58, "connections": 68, "disk_usage_pct": 82, "wal_segments_pending": 30, "write_iops": 1200},
            {"timestamp": "2026-04-06T09:45:00Z", "cpu_pct": 38, "mem_pct": 59, "connections": 70, "disk_usage_pct": 91, "wal_segments_pending": 80, "write_iops": 600},
            {"timestamp": "2026-04-06T09:55:00Z", "cpu_pct": 40, "mem_pct": 60, "connections": 72, "disk_usage_pct": 99, "wal_segments_pending": 150, "write_iops": 50},
            {"timestamp": "2026-04-06T10:00:00Z", "cpu_pct": 0, "mem_pct": 0, "connections": 0, "disk_usage_pct": 100, "wal_segments_pending": 0, "write_iops": 0},
        ],
        "auth-service": [
            {"timestamp": "2026-04-06T09:55:00Z", "cpu_pct": 22, "mem_pct": 58, "latency_p50": 12, "latency_p99": 45, "error_rate": 0.001, "mtls_failure_rate": 0.0},
            {"timestamp": "2026-04-06T10:00:00Z", "cpu_pct": 24, "mem_pct": 59, "latency_p50": 14, "latency_p99": 320, "error_rate": 0.30, "mtls_failure_rate": 0.30},
        ],
        "cache-redis": [
            {"timestamp": "2026-04-06T09:55:00Z", "mem_gb": 1.2, "mem_pct": 30, "hit_ratio": 0.92, "connections": 45},
            {"timestamp": "2026-04-06T10:00:00Z", "mem_gb": 1.3, "mem_pct": 32, "hit_ratio": 0.88, "connections": 38},
        ],
        "notification-service": [
            {"timestamp": "2026-04-06T09:55:00Z", "cpu_pct": 10, "mem_pct": 28, "queue_depth": 12, "auth_validation_ms": 42, "emails_sent_per_min": 120},
            {"timestamp": "2026-04-06T10:00:00Z", "cpu_pct": 12, "mem_pct": 30, "queue_depth": 1200, "auth_validation_ms": 850, "emails_sent_per_min": 45},
        ],
        "api-gateway": [
            {"timestamp": "2026-04-06T09:58:00Z", "cpu_pct": 20, "mem_pct": 45, "latency_p50": 30, "latency_p99": 88, "error_rate": 0.002, "5xx_rate": 0.001},
            {"timestamp": "2026-04-06T10:00:00Z", "cpu_pct": 25, "mem_pct": 47, "latency_p50": 45, "latency_p99": 3500, "error_rate": 0.55, "5xx_rate": 0.52},
        ],
    },

    traces={
        "auth-service": [
            "Trace: POST /auth/verify (uid=user_7712, total=FAILED) — mTLS REJECTED",
            "  └─ TLS handshake failed: x509: certificate has expired (not after: 2026-04-06T09:59:59Z)",
            "",
            "Trace: POST /auth/token (uid=user_1101, total=13ms) — SUCCESS (cached TLS session)",
            "  ├─ auth-service.checkSessionCache()       3ms   (cache-redis HIT)",
            "  ├─ auth-service.generateToken()            8ms",
            "  └─ auth-service.writeResponse()             2ms",
        ],
        "user-service": [
            "Trace: GET /api/v2/user/profile (uid=user_5571, total=8ms) — FAILED",
            "  ├─ user-service.parseRequest()             2ms",
            "  ├─ user-service.queryDB()                  FAILED (db-postgres connection refused)",
            "  └─ user-service.returnError()               6ms  (503)",
        ],
    },

    deploy_history={
        "db-postgres": [
            "v15.4  deployed 2026-03-15T08:00:00Z  status=stable  (running 22 days until disk fill)",
        ],
        "auth-service": [
            "v2.14.0  deployed 2026-04-01T10:00:00Z  status=stable  (running 5 days, no deploy issues — cert expiry is separate from deploy)",
        ],
    },

    runbooks={
        "db-postgres": (
            "## db-postgres Runbook\n"
            "- Disk full / No space left on device: WAL accumulation is the most common cause.\n"
            "  Restart db-postgres to trigger WAL cleanup and reclaim space.\n"
            "- Connection refused: Database may have crashed. Check for PANIC in logs."
        ),
        "auth-service": (
            "## auth-service Runbook\n"
            "- mTLS / certificate errors: If logs show 'certificate has expired' or 'x509',\n"
            "  check if cert-manager has renewed the cert in the Kubernetes secret.\n"
            "  If the secret is updated but the process has old cert, restart the service.\n"
            "  Note: cached TLS sessions continue working, so failures are intermittent (~30%),\n"
            "  not 100%. This makes the issue subtle.\n"
            "- IMPORTANT: auth-service does NOT depend on db-postgres. If db-postgres is down\n"
            "  and auth-service is also degraded, these are SEPARATE issues."
        ),
        "notification-service": (
            "## notification-service Runbook\n"
            "- Queue backing up with intermittent auth failures: Check auth-service health.\n"
            "  notification-service validates sender auth via mTLS to auth-service.\n"
            "  If auth-service has cert issues, some validations fail intermittently."
        ),
    },

    configs={
        "auth-service": {
            "current": "MTLS_CERT_SECRET=auth-service-mtls\nMTLS_MIN_VERSION=1.2\nSESSION_CACHE_SIZE=5000\nCACHE_BACKEND=cache-redis",
            "previous": "MTLS_CERT_SECRET=auth-service-mtls\nMTLS_MIN_VERSION=1.2\nSESSION_CACHE_SIZE=5000\nCACHE_BACKEND=cache-redis",
            "diff": "No config changes. mTLS certificate was auto-renewed in secret auth-service-mtls by cert-manager at 09:58:00Z, but running process still holds expired cert in memory. Restart required to reload.",
        },
        "db-postgres": {
            "current": "max_connections=100\nshared_buffers=4GB\nwal_level=replica\narchive_mode=on",
            "previous": "max_connections=100\nshared_buffers=4GB\nwal_level=replica\narchive_mode=on",
            "diff": "No config changes. Disk filled due to WAL accumulation from archiver failure.",
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

    root_cause_services=["db-postgres", "auth-service"],
    root_cause_categories=[RootCauseCategory.DISK_FULL, RootCauseCategory.CERT_EXPIRY],
    required_fixes=[
        RequiredFix(action="restart_service", service="db-postgres"),
        RequiredFix(action="restart_service", service="auth-service"),
    ],
    diagnosis_keywords=[
        "db-postgres", "disk", "full", "space", "WAL", "disk_full",
        "auth-service", "certificate", "cert", "mTLS", "expired", "cert_expiry", "x509", "handshake",
    ],
    requires_multi_root_diagnosis=True,
    no_fix_score_cap=0.69,

    weights={
        "correct_service": 0.15,
        "correct_category": 0.10,
        "correct_fix": 0.15,
        "secondary_fix": 0.20,
        "diagnosis_text": 0.15,
        "investigation": 0.10,
        "wrong_penalty": 0.05,
    },
)
