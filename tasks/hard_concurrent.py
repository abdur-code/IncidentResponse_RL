"""
Task: Concurrent Faults with Misleading Evidence
To add a new task, copy this file, modify the SCENARIO definition, and place it in tasks/.
The task loader will auto-discover it.
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="hard",
    name="Concurrent Faults with Misleading Evidence",
    difficulty="hard",
    max_steps=35,
    incident_summary=(
        "SEV-1 incident declared at 04:00 UTC. Multiple services affected simultaneously. "
        "payment-service is completely down after a recent deploy. auth-service showing intermittent "
        "timeouts and session validation failures. notification-service queue backing up. "
        "user-service has config warnings. api-gateway showing >30% error rate across multiple "
        "endpoints. Need to identify ALL root causes and restore full system health."
    ),

    services={
        "api-gateway": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service", "user-service", "payment-service"],
            version="v1.12.0", replicas=3,
        ),
        "auth-service": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["cache-redis"],
            version="v2.14.0", replicas=2,
        ),
        "user-service": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=["db-postgres"],
            version="v4.2.1", replicas=2,
        ),
        "payment-service": ServiceConfig(
            status=ServiceStatus.DOWN, deps=["db-postgres"],
            version="v3.8.2", replicas=2, is_root_cause=True, fault_type="bad_deploy",
        ),
        "db-postgres": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=[],
            version="v15.4", replicas=1,
        ),
        "cache-redis": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=[],
            version="v7.2.4", replicas=1, is_root_cause=True, fault_type="memory_leak",
        ),
        "notification-service": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service"],
            version="v1.5.0", replicas=1,
        ),
    },

    initial_alerts=[
        "[ALERT SEV-1] api-gateway: error rate >30%, multiple downstream failures detected",
        "[ALERT SEV-1] payment-service: health check failing, 0/2 pods ready, CrashLoopBackOff",
        "[ALERT SEV-2] auth-service: intermittent 500 errors, session validation latency >3s",
        "[ALERT SEV-2] notification-service: email delivery queue depth >2000, processing stalled",
        "[ALERT SEV-3] user-service: config validation warning (non-critical)",
    ],

    logs={
        "payment-service": [
            "2026-04-06T04:00:00Z INFO  [payment-service] Deploying v3.8.2 (previous: v3.8.1)",
            "2026-04-06T04:00:01Z INFO  [payment-service] Container image pulled: registry.internal/payment-service:v3.8.2",
            "2026-04-06T04:00:02Z INFO  [payment-service] Pod payment-service-7d4f8b-xk9m2 starting...",
            "2026-04-06T04:00:03Z INFO  [payment-service] Starting health check sequence...",
            "2026-04-06T04:00:04Z INFO  [payment-service] Loading configuration from ConfigMap...",
            "2026-04-06T04:00:05Z INFO  [payment-service] Initializing payment validation module v2 (new in v3.8.2)",
            "2026-04-06T04:00:05Z ERROR [payment-service] NullPointerException in PaymentValidatorV2.initialize(): config.getValidationRules() returned null",
            "2026-04-06T04:00:05Z ERROR [payment-service] Stack trace:",
            "    at com.acme.payment.validator.PaymentValidatorV2.initialize(PaymentValidatorV2.java:42)",
            "    at com.acme.payment.bootstrap.ServiceBootstrap.initModules(ServiceBootstrap.java:118)",
            "    at com.acme.payment.bootstrap.ServiceBootstrap.start(ServiceBootstrap.java:55)",
            "    at com.acme.payment.Main.main(Main.java:12)",
            "2026-04-06T04:00:06Z FATAL [payment-service] Bootstrap failed: required module 'payment-validator-v2' could not initialize",
            "2026-04-06T04:00:06Z INFO  [payment-service] Shutdown hook triggered, cleaning up...",
            "2026-04-06T04:00:07Z INFO  [payment-service] Health check endpoint /healthz returning 503",
            "2026-04-06T04:00:10Z WARN  [payment-service] Kubernetes: pod payment-service-7d4f8b-xk9m2 failed readiness probe (1/3)",
            "2026-04-06T04:00:20Z WARN  [payment-service] Kubernetes: pod payment-service-7d4f8b-xk9m2 failed readiness probe (2/3)",
            "2026-04-06T04:00:30Z ERROR [payment-service] Kubernetes: pod payment-service-7d4f8b-xk9m2 marked NotReady, removed from service",
            "2026-04-06T04:00:31Z INFO  [payment-service] Kubernetes: restarting pod (CrashLoopBackOff)",
            "2026-04-06T04:00:35Z INFO  [payment-service] Starting health check sequence...",
            "2026-04-06T04:00:37Z ERROR [payment-service] NullPointerException in PaymentValidatorV2.initialize(): config.getValidationRules() returned null",
            "2026-04-06T04:00:37Z FATAL [payment-service] Bootstrap failed: required module 'payment-validator-v2' could not initialize",
            "2026-04-06T04:00:38Z INFO  [payment-service] Kubernetes: restarting pod (CrashLoopBackOff)",
            "2026-04-06T04:00:45Z INFO  [payment-service] Starting health check sequence...",
            "2026-04-06T04:00:47Z ERROR [payment-service] NullPointerException in PaymentValidatorV2.initialize(): config.getValidationRules() returned null",
            "2026-04-06T04:00:47Z FATAL [payment-service] Bootstrap failed: required module 'payment-validator-v2' could not initialize",
            "2026-04-06T04:01:00Z ERROR [payment-service] CrashLoopBackOff: backing off 60s before next restart",
            "2026-04-06T04:02:05Z INFO  [payment-service] Starting health check sequence...",
            "2026-04-06T04:02:07Z ERROR [payment-service] NullPointerException in PaymentValidatorV2.initialize(): config.getValidationRules() returned null",
            "2026-04-06T04:02:07Z FATAL [payment-service] Bootstrap failed: required module 'payment-validator-v2' could not initialize",
            "2026-04-06T04:02:10Z ERROR [payment-service] CrashLoopBackOff: backing off 120s before next restart",
        ],
        "cache-redis": [
            "2026-04-06T03:00:00Z INFO  [cache-redis] Memory usage: 2.8GB/4.0GB (70%) — within operational range",
            "2026-04-06T03:05:00Z INFO  [cache-redis] Memory usage: 2.9GB/4.0GB (72%)",
            "2026-04-06T03:10:00Z INFO  [cache-redis] Memory usage: 3.0GB/4.0GB (75%)",
            "2026-04-06T03:15:00Z INFO  [cache-redis] Memory usage: 3.1GB/4.0GB (77%)",
            "2026-04-06T03:20:00Z INFO  [cache-redis] Memory usage: 3.2GB/4.0GB (80%)",
            "2026-04-06T03:25:00Z INFO  [cache-redis] Memory usage: 3.3GB/4.0GB (82%)",
            "2026-04-06T03:30:00Z WARN  [cache-redis] Memory usage: 3.4GB/4.0GB (85%) — approaching maxmemory threshold",
            "2026-04-06T03:30:01Z INFO  [cache-redis] Eviction policy: allkeys-lru activated",
            "2026-04-06T03:30:05Z WARN  [cache-redis] Evicting 1200 keys/sec to maintain memory budget",
            "2026-04-06T03:35:00Z WARN  [cache-redis] Memory usage: 3.5GB/4.0GB (87%) despite active eviction",
            "2026-04-06T03:40:00Z WARN  [cache-redis] Memory usage: 3.6GB/4.0GB (90%)",
            "2026-04-06T03:45:00Z WARN  [cache-redis] Memory usage: 3.7GB/4.0GB (92%) despite active eviction",
            "2026-04-06T03:45:01Z WARN  [cache-redis] Eviction rate insufficient: incoming writes (2.1GB/hr) exceed eviction rate (1.5GB/hr)",
            "2026-04-06T03:45:02Z WARN  [cache-redis] Key namespace auth:session:* most affected — 60% of evictions from this prefix",
            "2026-04-06T03:50:00Z WARN  [cache-redis] Memory usage: 3.8GB/4.0GB (95%)",
            "2026-04-06T03:55:00Z ERROR [cache-redis] Memory usage: 3.82GB/4.0GB (95.5%)",
            "2026-04-06T04:00:00Z ERROR [cache-redis] Memory usage: 3.85GB/4.0GB (96%) — critical threshold",
            "2026-04-06T04:00:01Z ERROR [cache-redis] Rejecting 12% of SET commands due to memory pressure",
            "2026-04-06T04:00:02Z WARN  [cache-redis] Client auth-service reporting increased cache misses (hit ratio: 35%, normal: 90%)",
            "2026-04-06T04:00:05Z ERROR [cache-redis] Memory fragmentation ratio: 1.8 (healthy: <1.5) — possible memory leak in module",
            "2026-04-06T04:00:10Z WARN  [cache-redis] Resident memory growing despite aggressive eviction — suspect leaked allocations in Lua script engine",
            "2026-04-06T04:00:15Z ERROR [cache-redis] Rejecting 18% of SET commands due to memory pressure",
        ],
        "auth-service": [
            "2026-04-06T03:00:00Z INFO  [auth-service] Request: POST /auth/token uid=user_4421 -> cache HIT (12ms)",
            "2026-04-06T03:00:05Z INFO  [auth-service] Request: POST /auth/verify uid=user_8832 -> cache HIT (10ms)",
            "2026-04-06T03:15:00Z INFO  [auth-service] Request: POST /auth/token uid=user_3310 -> cache HIT (11ms)",
            "2026-04-06T03:30:00Z INFO  [auth-service] Request: POST /auth/token uid=user_5571 -> cache HIT (13ms)",
            "2026-04-06T03:45:00Z WARN  [auth-service] Cache miss for session sid=c9f21a — falling back to db-postgres lookup (280ms)",
            "2026-04-06T03:45:02Z INFO  [auth-service] Request: POST /auth/token uid=user_7712 -> cache HIT (14ms)",
            "2026-04-06T03:45:05Z WARN  [auth-service] Cache miss rate elevated: 45% (normal: <10%)",
            "2026-04-06T03:45:10Z WARN  [auth-service] Cache miss for session sid=d4e82b — falling back to db-postgres lookup (320ms)",
            "2026-04-06T03:50:00Z WARN  [auth-service] DB connection pool: 28/30 active (falling back to DB for most session lookups)",
            "2026-04-06T03:55:00Z WARN  [auth-service] Cache miss rate: 55% — DB fallback path overloaded",
            "2026-04-06T04:00:00Z ERROR [auth-service] Cache write rejected by redis: OOM command not allowed when used memory > maxmemory",
            "2026-04-06T04:00:01Z WARN  [auth-service] 65% of requests hitting DB fallback path — latency p99 = 3200ms",
            "2026-04-06T04:00:03Z ERROR [auth-service] Request timeout: POST /auth/verify uid=user_8832 (DB fallback overloaded)",
            "2026-04-06T04:00:05Z ERROR [auth-service] Request timeout: POST /auth/token uid=user_2209 (DB fallback overloaded)",
            "2026-04-06T04:00:08Z WARN  [auth-service] DB connection pool: 30/30 active (SATURATED)",
            "2026-04-06T04:00:10Z WARN  [auth-service] Degraded mode: session validation averaging 1800ms (SLA: 200ms)",
            "2026-04-06T04:00:15Z ERROR [auth-service] 5 request timeouts in last 60 seconds",
        ],
        "user-service": [
            "2026-04-06T03:30:00Z INFO  [user-service] Config reload triggered by configmap update",
            "2026-04-06T03:30:01Z WARN  [user-service] Config validation: feature flag 'enable_profile_v2' references unknown experiment 'profile_redesign_q2'",
            "2026-04-06T03:30:01Z WARN  [user-service] Config validation: deprecated field 'legacy_avatar_url' present — will be removed in v4.0",
            "2026-04-06T03:30:02Z INFO  [user-service] Config applied successfully (2 warnings, 0 errors)",
            "2026-04-06T03:30:03Z INFO  [user-service] All endpoints healthy, no service disruption during config reload",
            "2026-04-06T03:30:10Z INFO  [user-service] GET /users/profile uid=user_4421 -> 200 (28ms)",
            "2026-04-06T03:45:00Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (30ms)",
            "2026-04-06T03:45:05Z INFO  [user-service] PUT /users/profile uid=user_3310 -> 200 (82ms)",
            "2026-04-06T04:00:00Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (28ms)",
            "2026-04-06T04:00:01Z INFO  [user-service] PUT /users/profile uid=user_3310 -> 200 (95ms)",
            "2026-04-06T04:00:05Z INFO  [user-service] GET /users/settings uid=user_5571 -> 200 (26ms)",
            "2026-04-06T04:00:10Z INFO  [user-service] Health check /healthz -> 200 OK",
        ],
        "notification-service": [
            "2026-04-06T03:45:00Z INFO  [notification-service] Auth token validated for batch #4445 (48ms)",
            "2026-04-06T03:45:01Z INFO  [notification-service] Email batch #4445 sent successfully (15 emails)",
            "2026-04-06T04:00:00Z WARN  [notification-service] Auth token validation taking 2800ms (SLA: 500ms)",
            "2026-04-06T04:00:02Z WARN  [notification-service] Email delivery queue depth: 2400 (normal: <100)",
            "2026-04-06T04:00:05Z ERROR [notification-service] Failed to validate sender auth for notification batch #8832 — auth-service timeout",
            "2026-04-06T04:00:06Z WARN  [notification-service] Pausing email delivery until auth validation recovers",
            "2026-04-06T04:00:10Z WARN  [notification-service] Queue depth growing: 2800 pending emails",
            "2026-04-06T04:00:15Z ERROR [notification-service] Auth validation timeout for batch #8833",
            "2026-04-06T04:00:20Z WARN  [notification-service] Queue depth: 3200 — SLA breach imminent for time-sensitive notifications",
        ],
        "api-gateway": [
            "2026-04-06T03:59:55Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 45ms)",
            "2026-04-06T03:59:58Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 92ms)",
            "2026-04-06T04:00:01Z ERROR [api-gateway] Route: POST /api/v2/pay -> payment-service (503, connection refused)",
            "2026-04-06T04:00:02Z WARN  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 1800ms) — slow",
            "2026-04-06T04:00:03Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 28ms)",
            "2026-04-06T04:00:05Z ERROR [api-gateway] Route: POST /api/v2/pay -> payment-service (503, connection refused)",
            "2026-04-06T04:00:06Z WARN  [api-gateway] Circuit breaker OPEN for payment-service (failures=5, threshold=5)",
            "2026-04-06T04:00:08Z ERROR [api-gateway] Route: POST /api/v2/verify -> auth-service (504, timeout after 5000ms)",
            "2026-04-06T04:00:10Z INFO  [api-gateway] Route: GET /api/v2/user/settings -> user-service (200, 25ms)",
            "2026-04-06T04:00:12Z ERROR [api-gateway] Route: POST /api/v2/pay -> payment-service (503, circuit breaker open)",
            "2026-04-06T04:00:15Z WARN  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 3200ms) — very slow",
            "2026-04-06T04:00:18Z ERROR [api-gateway] Route: POST /api/v2/verify -> auth-service (504, timeout after 5000ms)",
            "2026-04-06T04:00:20Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms)",
        ],
        "db-postgres": [
            "2026-04-06T03:55:00Z INFO  [db-postgres] Active connections: 42/100",
            "2026-04-06T04:00:00Z INFO  [db-postgres] Active connections: 58/100",
            "2026-04-06T04:00:01Z INFO  [db-postgres] Checkpoint starting: time-based",
            "2026-04-06T04:00:03Z INFO  [db-postgres] Checkpoint complete: wrote 1450 buffers (9.8%)",
            "2026-04-06T04:00:05Z INFO  [db-postgres] Higher than normal read load — auth-service fallback queries detected",
            "2026-04-06T04:00:10Z INFO  [db-postgres] Active connections: 62/100 — elevated but within limits",
            "2026-04-06T04:00:15Z INFO  [db-postgres] No deadlocks detected. Lock wait queue empty.",
            "2026-04-06T04:00:20Z INFO  [db-postgres] Autovacuum: processing table sessions (dead tuples: 850)",
        ],
    },

    metrics={
        "payment-service": [
            {"timestamp": "2026-04-06T03:55:00Z", "cpu_pct": 18, "mem_pct": 40, "latency_p50": 88, "latency_p99": 155, "error_rate": 0.001, "pods_ready": 2, "pods_total": 2},
            {"timestamp": "2026-04-06T04:00:00Z", "cpu_pct": 0, "mem_pct": 0, "latency_p50": 0, "latency_p99": 0, "error_rate": 1.0, "pods_ready": 0, "pods_total": 2},
        ],
        "cache-redis": [
            {"timestamp": "2026-04-06T02:00:00Z", "mem_gb": 2.4, "mem_pct": 60, "hit_ratio": 0.92, "evictions_per_s": 0, "connections": 45, "fragmentation_ratio": 1.1},
            {"timestamp": "2026-04-06T02:30:00Z", "mem_gb": 2.6, "mem_pct": 65, "hit_ratio": 0.91, "evictions_per_s": 0, "connections": 46, "fragmentation_ratio": 1.2},
            {"timestamp": "2026-04-06T03:00:00Z", "mem_gb": 2.8, "mem_pct": 70, "hit_ratio": 0.90, "evictions_per_s": 5, "connections": 47, "fragmentation_ratio": 1.3},
            {"timestamp": "2026-04-06T03:30:00Z", "mem_gb": 3.4, "mem_pct": 85, "hit_ratio": 0.72, "evictions_per_s": 1200, "connections": 48, "fragmentation_ratio": 1.5},
            {"timestamp": "2026-04-06T03:45:00Z", "mem_gb": 3.7, "mem_pct": 92, "hit_ratio": 0.55, "evictions_per_s": 1800, "connections": 48, "fragmentation_ratio": 1.7},
            {"timestamp": "2026-04-06T04:00:00Z", "mem_gb": 3.85, "mem_pct": 96, "hit_ratio": 0.35, "evictions_per_s": 2200, "connections": 47, "fragmentation_ratio": 1.8},
        ],
        "auth-service": [
            {"timestamp": "2026-04-06T03:00:00Z", "cpu_pct": 22, "mem_pct": 58, "latency_p50": 12, "latency_p99": 45, "error_rate": 0.001, "cache_hit_ratio": 0.90, "db_fallback_pct": 0.10},
            {"timestamp": "2026-04-06T03:30:00Z", "cpu_pct": 28, "mem_pct": 60, "latency_p50": 25, "latency_p99": 180, "error_rate": 0.005, "cache_hit_ratio": 0.72, "db_fallback_pct": 0.28},
            {"timestamp": "2026-04-06T03:45:00Z", "cpu_pct": 35, "mem_pct": 62, "latency_p50": 120, "latency_p99": 1200, "error_rate": 0.05, "cache_hit_ratio": 0.55, "db_fallback_pct": 0.45},
            {"timestamp": "2026-04-06T04:00:00Z", "cpu_pct": 42, "mem_pct": 65, "latency_p50": 800, "latency_p99": 3200, "error_rate": 0.15, "cache_hit_ratio": 0.35, "db_fallback_pct": 0.65},
        ],
        "user-service": [
            {"timestamp": "2026-04-06T03:00:00Z", "cpu_pct": 15, "mem_pct": 35, "latency_p50": 28, "latency_p99": 75, "error_rate": 0.001},
            {"timestamp": "2026-04-06T04:00:00Z", "cpu_pct": 15, "mem_pct": 35, "latency_p50": 30, "latency_p99": 82, "error_rate": 0.001},
        ],
        "notification-service": [
            {"timestamp": "2026-04-06T03:45:00Z", "cpu_pct": 12, "mem_pct": 30, "queue_depth": 15, "auth_validation_ms": 48, "emails_sent_per_min": 120},
            {"timestamp": "2026-04-06T04:00:00Z", "cpu_pct": 14, "mem_pct": 32, "queue_depth": 2400, "auth_validation_ms": 2800, "emails_sent_per_min": 5},
        ],
        "api-gateway": [
            {"timestamp": "2026-04-06T03:55:00Z", "cpu_pct": 20, "mem_pct": 45, "latency_p50": 35, "latency_p99": 95, "error_rate": 0.002, "5xx_rate": 0.001},
            {"timestamp": "2026-04-06T04:00:00Z", "cpu_pct": 28, "mem_pct": 48, "latency_p50": 120, "latency_p99": 5200, "error_rate": 0.35, "5xx_rate": 0.32},
        ],
        "db-postgres": [
            {"timestamp": "2026-04-06T03:55:00Z", "cpu_pct": 35, "mem_pct": 55, "connections": 42, "active_locks": 2, "deadlocks": 0, "write_iops": 1200, "read_iops": 3500},
            {"timestamp": "2026-04-06T04:00:00Z", "cpu_pct": 45, "mem_pct": 58, "connections": 62, "active_locks": 3, "deadlocks": 0, "write_iops": 1100, "read_iops": 4800},
        ],
    },

    traces={
        "payment-service": [
            "No recent traces — service is down (CrashLoopBackOff). Last successful trace (before deploy):",
            "Trace: POST /api/v2/pay (txn=pay_9901, total=92ms) — v3.8.1",
            "  ├─ payment-service.validateRequest()      8ms",
            "  ├─ payment-service.checkBalance()         25ms  (SELECT -> db-postgres)",
            "  ├─ payment-service.insertTransaction()    40ms  (INSERT -> db-postgres)",
            "  └─ payment-service.sendConfirmation()     19ms",
        ],
        "auth-service": [
            "Trace: POST /auth/verify (uid=user_8832, total=3200ms)",
            "  ├─ auth-service.checkSessionCache()       8ms    (cache-redis MISS)",
            "  ├─ auth-service.fallbackDBLookup()        2900ms (db-postgres — under load from fallback traffic)",
            "  ├─ auth-service.validateToken()            45ms",
            "  └─ auth-service.writeBackToCache()         FAILED (redis OOM rejected write)",
        ],
        "notification-service": [
            "Trace: POST /notifications/send (batch=#8832, total=5200ms) — TIMEOUT",
            "  ├─ notification-service.prepareBatch()     12ms",
            "  ├─ notification-service.validateAuth()     5000ms (-> auth-service TIMEOUT)",
            "  └─ notification-service.sendEmails()       never reached",
        ],
    },

    deploy_history={
        "payment-service": [
            "v3.8.2  deployed 2026-04-06T04:00:00Z  status=CrashLoopBackOff  (deployed 15 min ago)",
            "v3.8.1  deployed 2026-04-03T14:00:00Z  status=superseded  (was stable for 3 days)",
            "v3.8.0  deployed 2026-03-28T10:00:00Z  status=superseded",
        ],
        "auth-service": [
            "v2.14.0  deployed 2026-04-01T10:00:00Z  status=stable  (running 5 days, no issues)",
        ],
        "cache-redis": [
            "v7.2.4  deployed 2026-03-20T09:00:00Z  status=stable  (running 17 days)",
        ],
        "user-service": [
            "v4.2.1  deployed 2026-04-05T16:00:00Z  status=stable  (running 12 hours)",
        ],
    },

    runbooks={
        "payment-service": (
            "## payment-service Runbook\n"
            "- Crash on startup / CrashLoopBackOff: Check recent deploys. If the latest deploy\n"
            "  introduced the crash, rollback to previous known-good version:\n"
            "  rollback_deploy(service='payment-service', target_version='<previous_version>')\n"
            "  Check deploy history for the last stable version.\n"
            "- Transaction timeouts: Check db-postgres connection pool and lock status.\n"
            "- High latency: Check downstream service health (db-postgres)."
        ),
        "cache-redis": (
            "## cache-redis Runbook\n"
            "- Memory pressure / approaching maxmemory: Check memory trend in metrics.\n"
            "  If memory grows despite eviction, likely a memory leak.\n"
            "  Short-term fix: restart_service to clear leaked memory.\n"
            "  Alternative: scale_up to add more replicas and distribute load.\n"
            "- Elevated miss ratio: If caused by memory pressure/eviction storm, fix memory issue first.\n"
            "  If caused by TTL expiry batch, wait for cache to warm back up."
        ),
        "auth-service": (
            "## auth-service Runbook\n"
            "- High latency / DB fallback: Check cache-redis health. If redis is degraded,\n"
            "  auth-service falls back to DB lookups which are 10-50x slower.\n"
            "  Fix redis first — auth-service will recover automatically.\n"
            "- Cache write failures: Redis may be rejecting writes due to OOM. Check redis memory."
        ),
        "notification-service": (
            "## notification-service Runbook\n"
            "- Queue backing up: Usually caused by auth-service degradation. Notification-service\n"
            "  validates sender auth before sending. If auth is slow, queue grows.\n"
            "  Fix auth-service first — queue will drain automatically."
        ),
    },

    configs={
        "payment-service": {
            "current": "DB_POOL_SIZE=50\nDB_TIMEOUT=5000\nRETRY_COUNT=3\nVALIDATOR_VERSION=v2\nFEATURE_NEW_VALIDATION=true",
            "previous": "DB_POOL_SIZE=50\nDB_TIMEOUT=5000\nRETRY_COUNT=3\nVALIDATOR_VERSION=v1\nFEATURE_NEW_VALIDATION=false",
            "diff": "Changed VALIDATOR_VERSION from v1 to v2, enabled FEATURE_NEW_VALIDATION (part of v3.8.2 deploy)",
        },
        "user-service": {
            "current": "FEATURE_PROFILE_V2=true\nLEGACY_AVATAR_URL=https://cdn.example.com/avatars\nDB_POOL_SIZE=30",
            "previous": "FEATURE_PROFILE_V2=false\nDB_POOL_SIZE=30",
            "diff": "Added FEATURE_PROFILE_V2=true and LEGACY_AVATAR_URL (config change 30 min ago). 2 validation warnings but applied successfully.",
        },
        "cache-redis": {
            "current": "maxmemory=4gb\nmaxmemory-policy=allkeys-lru\ntimeout=300\ntcp-keepalive=60",
            "previous": "maxmemory=4gb\nmaxmemory-policy=allkeys-lru\ntimeout=300\ntcp-keepalive=60",
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

    root_cause_services=["payment-service", "cache-redis"],
    root_cause_categories=[RootCauseCategory.BAD_DEPLOY, RootCauseCategory.MEMORY_LEAK],
    required_fixes=[
        RequiredFix(action="rollback_deploy", service="payment-service", target_version="v3.8.1"),
        RequiredFix(action="restart_service", service="cache-redis"),
    ],
    diagnosis_keywords=[
        "payment-service", "deploy", "rollback", "v3.8.2", "v3.8.1", "NullPointerException", "crash",
        "cache-redis", "memory", "leak", "eviction", "auth-service", "fallback",
    ],

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

