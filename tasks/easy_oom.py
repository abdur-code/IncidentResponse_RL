"""
Task: Single Service OOM Crash
To add a new task, copy this file, modify the SCENARIO definition, and place it in tasks/.
The task loader will auto-discover it.
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="easy",
    name="Single Service OOM Crash",
    difficulty="easy",
    max_steps=15,
    incident_summary=(
        "PagerDuty alert fired at 02:15 UTC. auth-service is down with elevated error rates "
        "and pod restarts. api-gateway reporting 503s on login endpoints. Other services appear "
        "unaffected. On-call engineer needed to investigate and restore service."
    ),

    services={
        "api-gateway": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service", "user-service", "payment-service"],
            version="v1.12.0", replicas=3,
        ),
        "auth-service": ServiceConfig(
            status=ServiceStatus.DOWN, deps=["cache-redis"],
            version="v2.14.0", replicas=2, is_root_cause=True, fault_type="oom_crash",
        ),
        "user-service": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=["db-postgres"],
            version="v4.2.1", replicas=2,
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
        "[ALERT SEV-2] auth-service: error rate >50%, pod restarts detected (3 restarts in 5m)",
        "[ALERT SEV-3] api-gateway: elevated 503 responses on /api/v2/login and /api/v2/verify",
    ],

    logs={
        "auth-service": [
            "2026-04-06T02:10:01Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8832 latency=45ms",
            "2026-04-06T02:10:02Z INFO  [auth-service] Request processed: POST /auth/token uid=user_1204 latency=52ms",
            "2026-04-06T02:10:03Z INFO  [auth-service] Cache hit for session sid=a8f32c, returning cached token",
            "2026-04-06T02:10:04Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_6650 latency=41ms",
            "2026-04-06T02:10:05Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_3310 latency=38ms",
            "2026-04-06T02:10:06Z INFO  [auth-service] Cache hit for session sid=b2e19f, returning cached token",
            "2026-04-06T02:10:07Z INFO  [auth-service] Request processed: POST /auth/token uid=user_7712 latency=48ms",
            "2026-04-06T02:10:08Z DEBUG [auth-service] GC pause: 120ms (heap=1.8GB/2.0GB)",
            "2026-04-06T02:10:09Z INFO  [auth-service] Request processed: POST /auth/token uid=user_2290 latency=155ms",
            "2026-04-06T02:10:10Z INFO  [auth-service] Request processed: POST /auth/token uid=user_5571 latency=310ms",
            "2026-04-06T02:10:11Z WARN  [auth-service] Heap usage at 91% (1.82GB/2.0GB), approaching limit",
            "2026-04-06T02:10:12Z INFO  [auth-service] Request processed: POST /auth/token uid=user_9912 latency=580ms",
            "2026-04-06T02:10:13Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_4105 latency=620ms",
            "2026-04-06T02:10:14Z WARN  [auth-service] GC overhead limit exceeded, full GC triggered (heap=1.95GB/2.0GB)",
            "2026-04-06T02:10:15Z INFO  [auth-service] Full GC completed in 2100ms, freed 50MB",
            "2026-04-06T02:10:16Z INFO  [auth-service] Request processed: POST /auth/token uid=user_4423 latency=2400ms",
            "2026-04-06T02:10:17Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_8001 latency=1900ms",
            "2026-04-06T02:10:18Z ERROR [auth-service] OutOfMemoryError: unable to allocate 64MB for token cache expansion",
            "2026-04-06T02:10:18Z ERROR [auth-service] Worker pid=1842 killed by OOM killer (resident=2.01GB, limit=2.0GB)",
            "2026-04-06T02:10:19Z WARN  [auth-service] Process supervisor restarting worker (attempt 1/3)",
            "2026-04-06T02:10:22Z INFO  [auth-service] Worker pid=1901 started, initializing token cache...",
            "2026-04-06T02:10:25Z INFO  [auth-service] Request processed: POST /auth/token uid=user_7781 latency=65ms",
            "2026-04-06T02:10:28Z INFO  [auth-service] Request processed: POST /auth/token uid=user_2209 latency=72ms",
            "2026-04-06T02:10:30Z INFO  [auth-service] Cache hit for session sid=f8a21c, returning cached token",
            "2026-04-06T02:10:33Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_3390 latency=55ms",
            "2026-04-06T02:10:35Z INFO  [auth-service] Request processed: POST /auth/token uid=user_1150 latency=68ms",
            "2026-04-06T02:10:40Z INFO  [auth-service] Request processed: POST /auth/token uid=user_4482 latency=75ms",
            "2026-04-06T02:10:45Z DEBUG [auth-service] GC pause: 85ms (heap=1.5GB/2.0GB)",
            "2026-04-06T02:11:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_6633 latency=90ms",
            "2026-04-06T02:11:30Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_9901 latency=110ms",
            "2026-04-06T02:12:00Z WARN  [auth-service] Heap usage at 82% (1.64GB/2.0GB) — growing again after restart",
            "2026-04-06T02:12:30Z INFO  [auth-service] Request processed: POST /auth/token uid=user_5510 latency=180ms",
            "2026-04-06T02:12:45Z WARN  [auth-service] Heap usage at 88% (1.76GB/2.0GB) — growing linearly",
            "2026-04-06T02:13:00Z DEBUG [auth-service] GC pause: 350ms (heap=1.85GB/2.0GB)",
            "2026-04-06T02:13:05Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8820 latency=890ms",
            "2026-04-06T02:13:10Z ERROR [auth-service] OutOfMemoryError: unable to allocate 32MB for request buffer",
            "2026-04-06T02:13:10Z ERROR [auth-service] Worker pid=1901 killed by OOM killer (resident=1.98GB, limit=2.0GB)",
            "2026-04-06T02:13:11Z WARN  [auth-service] Process supervisor restarting worker (attempt 2/3)",
            "2026-04-06T02:13:14Z INFO  [auth-service] Worker pid=1955 started, initializing token cache...",
            "2026-04-06T02:13:20Z INFO  [auth-service] Request processed: POST /auth/token uid=user_1122 latency=58ms",
            "2026-04-06T02:13:45Z WARN  [auth-service] Heap usage at 80% (1.60GB/2.0GB)",
            "2026-04-06T02:14:15Z WARN  [auth-service] Heap usage at 87% (1.74GB/2.0GB)",
            "2026-04-06T02:14:45Z WARN  [auth-service] GC overhead limit exceeded, full GC triggered",
            "2026-04-06T02:15:00Z INFO  [auth-service] Full GC completed in 2800ms, freed 30MB — diminishing returns",
            "2026-04-06T02:15:20Z ERROR [auth-service] OutOfMemoryError: Java heap space",
            "2026-04-06T02:15:33Z ERROR [auth-service] Worker pid=1955 killed by OOM killer (resident=2.03GB, limit=2.0GB)",
            "2026-04-06T02:15:34Z ERROR [auth-service] Process supervisor: all 3 restart attempts exhausted",
            "2026-04-06T02:15:34Z FATAL [auth-service] Service entering crash loop backoff — no healthy workers remaining",
            "2026-04-06T02:15:35Z ERROR [auth-service] Health check failed: connection refused on :8080/healthz",
        ],
        "api-gateway": [
            "2026-04-06T02:10:01Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 48ms)",
            "2026-04-06T02:10:02Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 32ms)",
            "2026-04-06T02:10:03Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 95ms)",
            "2026-04-06T02:10:05Z INFO  [api-gateway] Route: GET /api/v2/user/settings -> user-service (200, 28ms)",
            "2026-04-06T02:10:08Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 155ms)",
            "2026-04-06T02:10:10Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 320ms)",
            "2026-04-06T02:10:15Z WARN  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 2500ms) — slow",
            "2026-04-06T02:10:18Z ERROR [api-gateway] Route: POST /api/v2/login -> auth-service (503, timeout after 5000ms)",
            "2026-04-06T02:10:20Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms)",
            "2026-04-06T02:10:22Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 68ms)",
            "2026-04-06T02:10:25Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 88ms)",
            "2026-04-06T02:13:10Z ERROR [api-gateway] Route: POST /api/v2/login -> auth-service (503, timeout after 5000ms)",
            "2026-04-06T02:13:12Z WARN  [api-gateway] Retrying auth-service request (attempt 2/3)",
            "2026-04-06T02:13:17Z ERROR [api-gateway] Route: POST /api/v2/login -> auth-service (503, timeout after 5000ms)",
            "2026-04-06T02:15:35Z ERROR [api-gateway] Route: POST /api/v2/login -> auth-service (503, connection refused)",
            "2026-04-06T02:15:36Z WARN  [api-gateway] Circuit breaker OPEN for auth-service (failures=10, threshold=5)",
            "2026-04-06T02:15:37Z ERROR [api-gateway] Route: POST /api/v2/login -> auth-service (503, circuit breaker open)",
            "2026-04-06T02:15:37Z ERROR [api-gateway] Route: POST /api/v2/verify -> auth-service (503, circuit breaker open)",
            "2026-04-06T02:15:38Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 28ms)",
            "2026-04-06T02:15:40Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 95ms)",
            "2026-04-06T02:15:42Z INFO  [api-gateway] Route: GET /api/v2/user/settings -> user-service (200, 25ms)",
        ],
        "user-service": [
            "2026-04-06T02:10:01Z INFO  [user-service] GET /users/profile uid=user_4421 -> 200 (32ms)",
            "2026-04-06T02:10:05Z INFO  [user-service] GET /users/settings uid=user_8832 -> 200 (28ms)",
            "2026-04-06T02:10:10Z INFO  [user-service] PUT /users/profile uid=user_3310 -> 200 (85ms)",
            "2026-04-06T02:10:15Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (30ms)",
            "2026-04-06T02:10:20Z INFO  [user-service] GET /users/profile uid=user_5571 -> 200 (27ms)",
            "2026-04-06T02:15:00Z INFO  [user-service] GET /users/profile uid=user_7712 -> 200 (31ms)",
            "2026-04-06T02:15:30Z INFO  [user-service] PUT /users/settings uid=user_2209 -> 200 (78ms)",
            "2026-04-06T02:15:35Z INFO  [user-service] GET /users/profile uid=user_9901 -> 200 (26ms)",
        ],
        "payment-service": [
            "2026-04-06T02:10:01Z INFO  [payment-service] Processing payment txn=pay_8832 amount=$45.00 -> db-postgres",
            "2026-04-06T02:10:02Z INFO  [payment-service] Payment completed txn=pay_8832 latency=85ms",
            "2026-04-06T02:10:10Z INFO  [payment-service] Processing payment txn=pay_1120 amount=$12.99 -> db-postgres",
            "2026-04-06T02:10:10Z INFO  [payment-service] Payment completed txn=pay_1120 latency=92ms",
            "2026-04-06T02:15:00Z INFO  [payment-service] Processing payment txn=pay_4455 amount=$78.50 -> db-postgres",
            "2026-04-06T02:15:01Z INFO  [payment-service] Payment completed txn=pay_4455 latency=88ms",
            "2026-04-06T02:15:30Z INFO  [payment-service] Health check /healthz -> 200 OK",
        ],
        "db-postgres": [
            "2026-04-06T02:00:00Z INFO  [db-postgres] Checkpoint starting: time-based",
            "2026-04-06T02:00:02Z INFO  [db-postgres] Checkpoint complete: wrote 842 buffers (5.7%)",
            "2026-04-06T02:10:00Z INFO  [db-postgres] Active connections: 35/100",
            "2026-04-06T02:10:01Z INFO  [db-postgres] Autovacuum: processing table users (dead tuples: 120)",
            "2026-04-06T02:15:00Z INFO  [db-postgres] Active connections: 34/100",
            "2026-04-06T02:15:01Z INFO  [db-postgres] Checkpoint starting: time-based",
            "2026-04-06T02:15:03Z INFO  [db-postgres] Checkpoint complete: wrote 910 buffers (6.2%)",
        ],
        "cache-redis": [
            "2026-04-06T02:10:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T02:10:01Z INFO  [cache-redis] Cache hit ratio: 92% (within normal range 85-95%)",
            "2026-04-06T02:10:05Z INFO  [cache-redis] Connected clients: 45",
            "2026-04-06T02:15:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T02:15:01Z INFO  [cache-redis] Cache hit ratio: 91%",
            "2026-04-06T02:15:05Z INFO  [cache-redis] Key evictions: 0 in last 5m",
        ],
        "notification-service": [
            "2026-04-06T02:10:00Z INFO  [notification-service] Email batch #4420 sent successfully (12 emails)",
            "2026-04-06T02:10:05Z INFO  [notification-service] Auth token validated for batch #4421 (45ms)",
            "2026-04-06T02:15:00Z INFO  [notification-service] Email batch #4425 sent successfully (8 emails)",
            "2026-04-06T02:15:30Z INFO  [notification-service] Health check /healthz -> 200 OK",
        ],
    },

    metrics={
        "auth-service": [
            {"timestamp": "2026-04-06T02:00:00Z", "cpu_pct": 25, "mem_pct": 60, "heap_gb": 1.2, "latency_p50": 45, "latency_p99": 120, "error_rate": 0.001, "restarts": 0, "connections": 150},
            {"timestamp": "2026-04-06T02:05:00Z", "cpu_pct": 30, "mem_pct": 72, "heap_gb": 1.44, "latency_p50": 52, "latency_p99": 180, "error_rate": 0.002, "restarts": 0, "connections": 155},
            {"timestamp": "2026-04-06T02:10:00Z", "cpu_pct": 45, "mem_pct": 91, "heap_gb": 1.82, "latency_p50": 310, "latency_p99": 2400, "error_rate": 0.15, "restarts": 1, "connections": 148},
            {"timestamp": "2026-04-06T02:11:00Z", "cpu_pct": 35, "mem_pct": 65, "heap_gb": 1.30, "latency_p50": 65, "latency_p99": 200, "error_rate": 0.02, "restarts": 1, "connections": 140},
            {"timestamp": "2026-04-06T02:13:00Z", "cpu_pct": 48, "mem_pct": 94, "heap_gb": 1.88, "latency_p50": 450, "latency_p99": 3100, "error_rate": 0.20, "restarts": 2, "connections": 130},
            {"timestamp": "2026-04-06T02:15:00Z", "cpu_pct": 0, "mem_pct": 0, "heap_gb": 0, "latency_p50": 0, "latency_p99": 0, "error_rate": 1.0, "restarts": 3, "connections": 0},
        ],
        "api-gateway": [
            {"timestamp": "2026-04-06T02:00:00Z", "cpu_pct": 20, "mem_pct": 45, "latency_p50": 32, "latency_p99": 85, "error_rate": 0.001, "5xx_rate": 0.001},
            {"timestamp": "2026-04-06T02:10:00Z", "cpu_pct": 22, "mem_pct": 46, "latency_p50": 35, "latency_p99": 95, "error_rate": 0.005, "5xx_rate": 0.003},
            {"timestamp": "2026-04-06T02:15:00Z", "cpu_pct": 25, "mem_pct": 48, "latency_p50": 40, "latency_p99": 5200, "error_rate": 0.42, "5xx_rate": 0.40},
        ],
        "user-service": [
            {"timestamp": "2026-04-06T02:00:00Z", "cpu_pct": 15, "mem_pct": 35, "latency_p50": 28, "latency_p99": 75, "error_rate": 0.001},
            {"timestamp": "2026-04-06T02:15:00Z", "cpu_pct": 15, "mem_pct": 35, "latency_p50": 29, "latency_p99": 78, "error_rate": 0.001},
        ],
        "payment-service": [
            {"timestamp": "2026-04-06T02:00:00Z", "cpu_pct": 18, "mem_pct": 40, "latency_p50": 85, "latency_p99": 150, "error_rate": 0.001},
            {"timestamp": "2026-04-06T02:15:00Z", "cpu_pct": 18, "mem_pct": 40, "latency_p50": 88, "latency_p99": 155, "error_rate": 0.001},
        ],
        "db-postgres": [
            {"timestamp": "2026-04-06T02:00:00Z", "cpu_pct": 30, "mem_pct": 55, "connections": 35, "active_locks": 2, "deadlocks": 0, "write_iops": 1200, "read_iops": 3500},
            {"timestamp": "2026-04-06T02:15:00Z", "cpu_pct": 32, "mem_pct": 55, "connections": 34, "active_locks": 2, "deadlocks": 0, "write_iops": 1150, "read_iops": 3400},
        ],
        "cache-redis": [
            {"timestamp": "2026-04-06T02:00:00Z", "mem_gb": 1.2, "mem_pct": 30, "hit_ratio": 0.92, "evictions_per_s": 0, "connections": 45},
            {"timestamp": "2026-04-06T02:15:00Z", "mem_gb": 1.2, "mem_pct": 30, "hit_ratio": 0.91, "evictions_per_s": 0, "connections": 45},
        ],
    },

    traces={
        "auth-service": [
            "No recent traces available — service is down. Last successful trace:",
            "Trace: POST /auth/token (uid=user_4423, total=2400ms) — BEFORE CRASH",
            "  ├─ auth-service.checkSessionCache()   5ms   (cache-redis HIT)",
            "  ├─ auth-service.generateToken()        45ms",
            "  ├─ auth-service.GC_FULL_PAUSE          2100ms  ← GC dominated total time",
            "  └─ auth-service.writeResponse()         250ms",
        ],
        "api-gateway": [
            "Trace: POST /api/v2/login (total=5005ms) — TIMEOUT",
            "  ├─ api-gateway.parseRequest()          2ms",
            "  ├─ api-gateway.routeToAuthService()    5000ms (TIMEOUT — auth-service unreachable)",
            "  └─ api-gateway.returnError()            3ms   (503 Service Unavailable)",
        ],
    },

    deploy_history={
        "auth-service": [
            "v2.14.0  deployed 2026-04-01T10:00:00Z  status=stable  (running 5 days, no issues)",
            "v2.13.2  deployed 2026-03-25T14:00:00Z  status=superseded",
        ],
        "api-gateway": [
            "v1.12.0  deployed 2026-03-28T09:00:00Z  status=stable  (running 9 days)",
        ],
        "user-service": [
            "v4.2.1  deployed 2026-04-05T16:00:00Z  status=stable  (running 10 hours)",
            "v4.2.0  deployed 2026-04-01T11:00:00Z  status=superseded",
        ],
        "payment-service": [
            "v3.8.1  deployed 2026-04-03T14:00:00Z  status=stable  (running 3 days)",
        ],
    },

    runbooks={
        "auth-service": (
            "## auth-service Runbook\n"
            "- OOM crashes: Check heap usage trends in metrics. If memory grows linearly after\n"
            "  restart, likely a memory leak in the token cache. Short-term fix: restart to clear\n"
            "  cached state. Long-term: file ticket for cache eviction policy fix.\n"
            "- High latency: Check cache-redis connectivity. Auth-service falls back to DB lookups\n"
            "  if cache is down, which increases latency 10x.\n"
            "- Connection refused: Service may be in crash loop. Check restart count and supervisor logs.\n"
            "- Token validation failures: Check if JWT signing key was recently rotated."
        ),
        "api-gateway": (
            "## api-gateway Runbook\n"
            "- 503 errors: Check downstream service health. Gateway proxies to auth-service,\n"
            "  user-service, and payment-service. Identify which downstream is failing.\n"
            "- Circuit breaker open: Downstream service has exceeded failure threshold.\n"
            "  Fix the downstream service; circuit breaker will auto-close after 30s of healthy responses.\n"
            "- High latency: Usually caused by slow downstream. Check traces to identify bottleneck."
        ),
    },

    configs={
        "auth-service": {
            "current": "JVM_HEAP_MAX=2g\nTOKEN_CACHE_SIZE=500000\nSESSION_TTL=3600\nREDIS_POOL_SIZE=20",
            "previous": "JVM_HEAP_MAX=2g\nTOKEN_CACHE_SIZE=500000\nSESSION_TTL=3600\nREDIS_POOL_SIZE=20",
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

    root_cause_services=["auth-service"],
    root_cause_categories=[RootCauseCategory.OOM_CRASH],
    required_fixes=[
        RequiredFix(action="restart_service", service="auth-service"),
    ],
    diagnosis_keywords=["auth-service", "oom", "out of memory", "memory", "crash", "restart"],

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

