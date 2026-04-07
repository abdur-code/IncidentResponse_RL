"""
Task: Network Partition + Rate Limiting (Concurrent Faults)

Two independent faults:
1. cache-redis is network-partitioned from app pods (10.0.1.0/24) but reachable
   from the monitoring subnet (10.0.3.0/24). It appears "healthy" in dashboards
   but has 0 connected clients. auth-service falls back to DB for all session lookups.
2. A config push reduced api-gateway's RATE_LIMIT_RPS from 1000 to 100. 60% of
   legitimate traffic gets 429 Too Many Requests.

Red herrings:
- cache-redis looks healthy on monitoring plane (normal CPU/memory) but 0 clients
- db-postgres elevated connections from auth-service fallback (not a db problem)
- notification-service queue growing (victim of auth-service degradation)
- user-service intermittent 429s (from api-gateway, not user-service)
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="hard_partition_ratelimit",
    name="Network Partition with Concurrent Rate Limiting",
    difficulty="hard",
    max_steps=35,
    incident_summary=(
        "SEV-1 declared at 09:00 UTC. Two distinct failure patterns observed: "
        "(1) api-gateway is rejecting ~60% of all incoming requests with 429 Too Many "
        "Requests even though actual traffic volume is normal; "
        "(2) auth-service cannot reach cache-redis and is falling back to db-postgres "
        "for session lookups, causing severe latency. notification-service email delivery "
        "stalled. user-service and payment-service appear to work when requests get through "
        "the gateway."
    ),

    services={
        "api-gateway": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service", "user-service", "payment-service"],
            version="v1.12.0", replicas=3, is_root_cause=True, fault_type="rate_limit",
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
            status=ServiceStatus.HEALTHY, deps=["db-postgres"],
            version="v3.8.1", replicas=2,
        ),
        "db-postgres": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=[],
            version="v15.4", replicas=1,
        ),
        "cache-redis": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=[],
            version="v7.2.4", replicas=1, is_root_cause=True, fault_type="network_partition",
        ),
        "notification-service": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service"],
            version="v1.5.0", replicas=1,
        ),
    },

    initial_alerts=[
        "[ALERT SEV-1] api-gateway: 60% of requests returning 429 Too Many Requests — rate limiter triggered",
        "[ALERT SEV-1] auth-service: session validation latency >5s, cache-redis connection timeout",
        "[ALERT SEV-2] notification-service: auth validation timing out, queue depth >5000",
        "[ALERT SEV-3] cache-redis: client connection count dropped to 0 (was 45)",
        "[ALERT SEV-3] user-service: intermittent 429 responses from api-gateway (informational)",
    ],

    logs={
        "api-gateway": [
            "2026-04-06T08:45:00Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 45ms)",
            "2026-04-06T08:48:00Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms)",
            "2026-04-06T08:50:00Z INFO  [api-gateway] Config reload: RATE_LIMIT_RPS updated from 1000 to 100",
            "2026-04-06T08:50:01Z WARN  [api-gateway] Rate limiter reconfigured: global limit now 100 requests/sec (was 1000)",
            "2026-04-06T08:50:02Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 42ms)",
            "2026-04-06T08:52:00Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 88ms)",
            "2026-04-06T08:55:00Z WARN  [api-gateway] Rate limit exceeded: 45 requests rejected in last 60s (limit: 100 rps, actual: 250 rps)",
            "2026-04-06T08:55:01Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 2800ms) — slow",
            "2026-04-06T08:58:00Z WARN  [api-gateway] Rate limit exceeded: 92 requests rejected in last 60s",
            "2026-04-06T09:00:00Z WARN  [api-gateway] Rate limit exceeded: 148 requests rejected in last 60s (limit: 100 rps, actual: 250 rps)",
            "2026-04-06T09:00:02Z ERROR [api-gateway] Route: POST /api/v2/login -> 429 Too Many Requests (rate limited)",
            "2026-04-06T09:00:03Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms) — passed rate limit",
            "2026-04-06T09:00:05Z ERROR [api-gateway] Route: POST /api/v2/pay -> 429 Too Many Requests (rate limited)",
            "2026-04-06T09:00:06Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 4500ms) — very slow",
            "2026-04-06T09:00:08Z WARN  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 4500ms) — very slow",
            "2026-04-06T09:00:10Z ERROR [api-gateway] Route: POST /api/v2/verify -> auth-service (504, timeout after 5000ms)",
            "2026-04-06T09:00:12Z ERROR [api-gateway] Route: POST /api/v2/login -> 429 Too Many Requests (rate limited)",
            "2026-04-06T09:00:15Z WARN  [api-gateway] Combined effect: 60% of requests either rate-limited (429) or timing out (504)",
            "2026-04-06T09:00:18Z INFO  [api-gateway] Note: actual traffic volume (250 rps) is within normal range — rate limit config may be incorrect",
            "2026-04-06T09:00:20Z WARN  [api-gateway] Corrected config pushed to configmap at 08:55 (RATE_LIMIT_RPS=1000) but process still has old value loaded",
        ],
        "cache-redis": [
            "2026-04-06T08:45:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T08:45:01Z INFO  [cache-redis] Connected clients: 45",
            "2026-04-06T08:45:02Z INFO  [cache-redis] Cache hit ratio: 92%",
            "2026-04-06T08:48:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T08:50:00Z WARN  [cache-redis] Client connection from 10.0.1.22 (auth-service) dropped: network unreachable",
            "2026-04-06T08:50:01Z WARN  [cache-redis] Client connection from 10.0.1.23 (auth-service) dropped: network unreachable",
            "2026-04-06T08:50:02Z WARN  [cache-redis] Client connection from 10.0.1.24 (notification-service) dropped: network unreachable",
            "2026-04-06T08:50:03Z WARN  [cache-redis] All client connections from 10.0.1.0/24 subnet lost",
            "2026-04-06T08:50:05Z INFO  [cache-redis] Connections from 10.0.3.0/24 (monitoring) still active",
            "2026-04-06T08:55:00Z INFO  [cache-redis] Responding to health check from 10.0.3.10 (monitoring) — 200 OK",
            "2026-04-06T08:55:01Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%) — no change, no traffic",
            "2026-04-06T09:00:00Z WARN  [cache-redis] Connected clients: 0 (monitoring checks still passing via 10.0.3.0/24 subnet)",
            "2026-04-06T09:00:01Z INFO  [cache-redis] Internal health: OK. CPU, memory, disk all normal.",
            "2026-04-06T09:00:05Z WARN  [cache-redis] No application traffic received in 10 minutes — possible network issue on pod network interface",
        ],
        "auth-service": [
            "2026-04-06T08:45:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8832 -> cache HIT (12ms)",
            "2026-04-06T08:48:00Z INFO  [auth-service] Cache hit for session sid=a8f32c, returning cached token",
            "2026-04-06T08:50:00Z ERROR [auth-service] Cache connection failed: connection timed out to cache-redis:6379 — no route to host 10.0.2.15",
            "2026-04-06T08:50:01Z WARN  [auth-service] Falling back to db-postgres for session lookups",
            "2026-04-06T08:50:02Z WARN  [auth-service] Cache reconnection attempt 1: timed out (no route to host)",
            "2026-04-06T08:50:05Z WARN  [auth-service] DB fallback: POST /auth/token uid=user_3310 latency=1200ms (normal via cache: 12ms)",
            "2026-04-06T08:52:00Z WARN  [auth-service] DB fallback: POST /auth/verify uid=user_5571 latency=1500ms",
            "2026-04-06T08:55:00Z ERROR [auth-service] Cache reconnection attempt 5: timed out — no route to host 10.0.2.15 (cache-redis)",
            "2026-04-06T08:55:01Z WARN  [auth-service] 100% of session lookups hitting DB fallback path",
            "2026-04-06T09:00:00Z WARN  [auth-service] Latency p99=5200ms — DB connection pool under heavy fallback load",
            "2026-04-06T09:00:02Z ERROR [auth-service] DB connection pool: 30/30 SATURATED from fallback traffic",
            "2026-04-06T09:00:05Z ERROR [auth-service] Request timeout: POST /auth/verify uid=user_1101 (pool exhaustion + slow queries)",
            "2026-04-06T09:00:08Z WARN  [auth-service] Error rate: 18% — pool exhaustion causing timeouts on new requests",
            "2026-04-06T09:00:10Z ERROR [auth-service] Cache reconnection attempt 12: timed out — giving up automatic reconnection",
        ],
        "notification-service": [
            "2026-04-06T08:48:00Z INFO  [notification-service] Email batch #5200 sent successfully (14 emails)",
            "2026-04-06T08:55:00Z WARN  [notification-service] Auth validation for batch #5205: 2800ms (SLA: 500ms)",
            "2026-04-06T08:58:00Z ERROR [notification-service] Auth validation timeout for batch #5208 (>5000ms)",
            "2026-04-06T09:00:00Z WARN  [notification-service] Auth validation timeout for batch #5210 (>5000ms)",
            "2026-04-06T09:00:05Z ERROR [notification-service] Failed to validate sender auth — auth-service timeout",
            "2026-04-06T09:00:08Z WARN  [notification-service] Queue depth: 5200 — email delivery stalled",
            "2026-04-06T09:00:10Z ERROR [notification-service] 8 consecutive auth validation timeouts — pausing all delivery",
            "2026-04-06T09:00:15Z WARN  [notification-service] Queue depth: 5800 — growing steadily",
        ],
        "db-postgres": [
            "2026-04-06T08:45:00Z INFO  [db-postgres] Active connections: 40/100",
            "2026-04-06T08:50:00Z INFO  [db-postgres] Active connections: 55/100 — auth-service fallback queries detected",
            "2026-04-06T08:55:00Z WARN  [db-postgres] Active connections: 72/100 — elevated (auth-service session lookups via DB)",
            "2026-04-06T09:00:00Z WARN  [db-postgres] Active connections: 85/100 — approaching limit due to auth-service DB fallback",
            "2026-04-06T09:00:02Z INFO  [db-postgres] Query performance nominal: no deadlocks, no lock contention",
            "2026-04-06T09:00:05Z INFO  [db-postgres] All queries completing within normal latency. Load is elevated but manageable.",
        ],
        "user-service": [
            "2026-04-06T09:00:00Z INFO  [user-service] GET /users/profile uid=user_4421 -> 200 (30ms)",
            "2026-04-06T09:00:03Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (28ms)",
            "2026-04-06T09:00:05Z WARN  [user-service] Some incoming requests being rate-limited by api-gateway (429 before reaching user-service)",
            "2026-04-06T09:00:10Z INFO  [user-service] Health check /healthz -> 200 OK. All internal systems healthy.",
        ],
        "payment-service": [
            "2026-04-06T09:00:00Z INFO  [payment-service] Processing payment txn=pay_8801 amount=$45.00 -> db-postgres",
            "2026-04-06T09:00:01Z INFO  [payment-service] Payment completed txn=pay_8801 latency=88ms",
            "2026-04-06T09:00:05Z INFO  [payment-service] Health check /healthz -> 200 OK",
        ],
    },

    metrics={
        "api-gateway": [
            {"timestamp": "2026-04-06T08:45:00Z", "cpu_pct": 20, "mem_pct": 45, "latency_p50": 35, "latency_p99": 90, "error_rate": 0.002, "5xx_rate": 0.001, "429_rate": 0.0, "rate_limit_rps_config": 1000},
            {"timestamp": "2026-04-06T08:55:00Z", "cpu_pct": 22, "mem_pct": 46, "latency_p50": 40, "latency_p99": 3200, "error_rate": 0.55, "5xx_rate": 0.12, "429_rate": 0.45, "rate_limit_rps_config": 100},
            {"timestamp": "2026-04-06T09:00:00Z", "cpu_pct": 25, "mem_pct": 47, "latency_p50": 50, "latency_p99": 5100, "error_rate": 0.62, "5xx_rate": 0.15, "429_rate": 0.48, "rate_limit_rps_config": 100},
        ],
        "cache-redis": [
            {"timestamp": "2026-04-06T08:45:00Z", "mem_gb": 1.2, "mem_pct": 30, "hit_ratio": 0.92, "connections": 45, "monitoring_reachable": True},
            {"timestamp": "2026-04-06T08:50:00Z", "mem_gb": 1.2, "mem_pct": 30, "hit_ratio": "N/A", "connections": 0, "monitoring_reachable": True},
            {"timestamp": "2026-04-06T09:00:00Z", "mem_gb": 1.2, "mem_pct": 30, "hit_ratio": "N/A", "connections": 0, "monitoring_reachable": True},
        ],
        "auth-service": [
            {"timestamp": "2026-04-06T08:45:00Z", "cpu_pct": 22, "mem_pct": 58, "latency_p50": 12, "latency_p99": 45, "error_rate": 0.001, "cache_hit_ratio": 0.92, "db_fallback_pct": 0.08},
            {"timestamp": "2026-04-06T08:55:00Z", "cpu_pct": 40, "mem_pct": 62, "latency_p50": 800, "latency_p99": 3200, "error_rate": 0.08, "cache_hit_ratio": 0.0, "db_fallback_pct": 1.0},
            {"timestamp": "2026-04-06T09:00:00Z", "cpu_pct": 45, "mem_pct": 65, "latency_p50": 1200, "latency_p99": 5200, "error_rate": 0.18, "cache_hit_ratio": 0.0, "db_fallback_pct": 1.0},
        ],
        "db-postgres": [
            {"timestamp": "2026-04-06T08:45:00Z", "cpu_pct": 30, "mem_pct": 55, "connections": 40, "deadlocks": 0, "write_iops": 1200, "read_iops": 3500},
            {"timestamp": "2026-04-06T09:00:00Z", "cpu_pct": 42, "mem_pct": 58, "connections": 85, "deadlocks": 0, "write_iops": 1100, "read_iops": 5200},
        ],
        "notification-service": [
            {"timestamp": "2026-04-06T08:48:00Z", "cpu_pct": 10, "mem_pct": 28, "queue_depth": 15, "auth_validation_ms": 42, "emails_sent_per_min": 120},
            {"timestamp": "2026-04-06T09:00:00Z", "cpu_pct": 12, "mem_pct": 30, "queue_depth": 5200, "auth_validation_ms": "timeout", "emails_sent_per_min": 0},
        ],
    },

    traces={
        "auth-service": [
            "Trace: POST /auth/verify (uid=user_1101, total=5200ms) — TIMEOUT",
            "  ├─ auth-service.checkSessionCache()       3000ms  (cache-redis TIMEOUT — no route to host)",
            "  ├─ auth-service.fallbackDBLookup()         2100ms  (db-postgres — pool wait + query)",
            "  ├─ auth-service.validateToken()             TIMEOUT (pool exhaustion, no connection available)",
            "  └─ auth-service.writeBackToCache()          never reached",
        ],
        "api-gateway": [
            "Trace: POST /api/v2/login (client=10.0.1.52, total=1ms) — REJECTED",
            "  └─ api-gateway.checkRateLimit()             1ms  (429 Too Many Requests — 250 rps > 100 rps limit)",
            "",
            "Trace: POST /api/v2/login (client=10.0.1.88, total=4600ms) — PASSED rate limit",
            "  ├─ api-gateway.checkRateLimit()             1ms  (passed)",
            "  ├─ api-gateway.routeToAuthService()         4500ms  (auth-service slow — DB fallback)",
            "  └─ api-gateway.returnResponse()              99ms",
        ],
    },

    deploy_history={
        "api-gateway": [
            "v1.12.0  deployed 2026-03-28T09:00:00Z  status=stable  (running 9 days, no recent deploy — config change only)",
        ],
        "cache-redis": [
            "v7.2.4  deployed 2026-03-20T09:00:00Z  status=stable  (running 17 days)",
        ],
    },

    runbooks={
        "api-gateway": (
            "## api-gateway Runbook\n"
            "- 429 Too Many Requests: Check RATE_LIMIT_RPS config value.\n"
            "  Normal traffic is ~250 rps. If limit is set below normal traffic,\n"
            "  legitimate requests get rejected. Use diff_config to check for recent changes.\n"
            "  If corrected config is in the configmap but process has old value, restart.\n"
            "- 504 timeouts: Downstream service is slow. Check auth-service latency."
        ),
        "cache-redis": (
            "## cache-redis Runbook\n"
            "- 0 connected clients but monitoring healthy: Possible network partition.\n"
            "  Pod network interface may be down while management/monitoring plane is up.\n"
            "  Restart cache-redis to rebind the network interface.\n"
            "- Verify by checking if monitoring (10.0.3.0/24) can reach it but app pods (10.0.1.0/24) cannot."
        ),
        "auth-service": (
            "## auth-service Runbook\n"
            "- High latency with DB fallback: auth-service depends on cache-redis for fast\n"
            "  session lookups. If cache-redis is unreachable, auth falls back to db-postgres\n"
            "  which is 100x slower. Fix cache-redis connectivity first."
        ),
    },

    configs={
        "api-gateway": {
            "current": "RATE_LIMIT_RPS=100\nRATE_LIMIT_BURST=20\nTIMEOUT_MS=5000",
            "previous": "RATE_LIMIT_RPS=1000\nRATE_LIMIT_BURST=200\nTIMEOUT_MS=5000",
            "diff": "RATE_LIMIT_RPS changed from 1000 to 100 (config push at 08:50). This reduced the rate limit by 10x, causing legitimate traffic (250 rps) to be throttled. The configmap was corrected at 08:55 but the running process still has the old (wrong) value. Restart required.",
        },
        "cache-redis": {
            "current": "maxmemory=4gb\nmaxmemory-policy=allkeys-lru\nbind=0.0.0.0\nprotected-mode=no",
            "previous": "maxmemory=4gb\nmaxmemory-policy=allkeys-lru\nbind=0.0.0.0\nprotected-mode=no",
            "diff": "No config changes. Network partition is at the infrastructure level (pod network interface), not a config issue.",
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

    root_cause_services=["cache-redis", "api-gateway"],
    root_cause_categories=[RootCauseCategory.NETWORK_PARTITION, RootCauseCategory.RATE_LIMIT],
    required_fixes=[
        RequiredFix(action="restart_service", service="cache-redis"),
        RequiredFix(action="restart_service", service="api-gateway"),
    ],
    diagnosis_keywords=[
        "cache-redis", "network", "partition", "unreachable", "no route",
        "api-gateway", "rate limit", "rate_limit", "429", "RATE_LIMIT_RPS", "config", "100",
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
