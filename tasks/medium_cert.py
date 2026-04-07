"""
Task: Expired TLS Certificate on API Gateway
api-gateway's TLS cert expires at 07:00. cert-manager auto-renewed in the secret
but the running process still has the old cert. ~40% of connections fail TLS handshake.

Red herrings:
- auth-service shows connection resets (victim, not cause)
- notification-service queue backing up (victim of auth-service)
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="medium_cert",
    name="Expired TLS Certificate Cascading Failures",
    difficulty="medium",
    max_steps=25,
    incident_summary=(
        "SEV-1 incident at 07:00 UTC. Broad-spectrum failures across the platform. "
        "api-gateway returning 502 and 503 errors on approximately 40% of all requests. "
        "auth-service showing connection resets. notification-service queue backing up. "
        "Pattern is unusual — failures affect all downstream services intermittently "
        "rather than one consistently."
    ),

    services={
        "api-gateway": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service", "user-service", "payment-service"],
            version="v1.12.0", replicas=3, is_root_cause=True, fault_type="cert_expiry",
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
            status=ServiceStatus.HEALTHY, deps=[],
            version="v7.2.4", replicas=1,
        ),
        "notification-service": ServiceConfig(
            status=ServiceStatus.DEGRADED, deps=["auth-service"],
            version="v1.5.0", replicas=1,
        ),
    },

    initial_alerts=[
        "[ALERT SEV-1] api-gateway: elevated 502/503 error rate across ALL endpoints (>40%)",
        "[ALERT SEV-2] auth-service: intermittent connection resets on inbound requests",
        "[ALERT SEV-2] notification-service: email delivery stalling, auth validation failures",
    ],

    logs={
        "api-gateway": [
            "2026-04-06T06:50:00Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 45ms)",
            "2026-04-06T06:52:00Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 32ms)",
            "2026-04-06T06:55:00Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 88ms)",
            "2026-04-06T06:58:00Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 42ms)",
            "2026-04-06T06:59:30Z INFO  [api-gateway] TLS certificate for *.api.example.com: 30 seconds until expiry",
            "2026-04-06T06:59:59Z WARN  [api-gateway] TLS certificate for *.api.example.com expires in 1 second",
            "2026-04-06T07:00:00Z ERROR [api-gateway] TLS handshake failed: certificate has expired (not after: 2026-04-06T06:59:59Z)",
            "2026-04-06T07:00:01Z ERROR [api-gateway] TLS handshake failed for client 10.0.1.52: x509: certificate has expired or is not yet valid",
            "2026-04-06T07:00:02Z WARN  [api-gateway] 42% of incoming connections failing TLS handshake",
            "2026-04-06T07:00:03Z ERROR [api-gateway] Upstream connection to auth-service reset during TLS renegotiation",
            "2026-04-06T07:00:04Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 44ms) — via cached TLS session",
            "2026-04-06T07:00:05Z ERROR [api-gateway] TLS handshake failed for client 10.0.1.88: x509: certificate has expired",
            "2026-04-06T07:00:06Z ERROR [api-gateway] Route: GET /api/v2/user/profile -> 502 Bad Gateway (TLS handshake failed)",
            "2026-04-06T07:00:08Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 90ms) — via cached TLS session",
            "2026-04-06T07:00:10Z WARN  [api-gateway] cert-manager renewed certificate in secret api-gateway-tls at 06:55:00Z but running process has old cert in memory",
            "2026-04-06T07:00:12Z INFO  [api-gateway] Note: service restart required to reload certificate from updated secret",
            "2026-04-06T07:00:15Z ERROR [api-gateway] 502 errors: 156 in last 60 seconds across all routes",
            "2026-04-06T07:00:18Z WARN  [api-gateway] Clients with cached TLS sessions still connecting successfully (~60% of requests)",
            "2026-04-06T07:00:20Z ERROR [api-gateway] TLS handshake failed for client 10.0.1.103: x509: certificate has expired",
            "2026-04-06T07:00:25Z ERROR [api-gateway] 502 error rate trending up as cached TLS sessions expire",
            "2026-04-06T07:00:30Z WARN  [api-gateway] Error rate now 48% — more clients forced to renegotiate TLS",
        ],
        "auth-service": [
            "2026-04-06T06:55:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8832 latency=42ms",
            "2026-04-06T06:58:00Z INFO  [auth-service] Cache hit for session sid=a8f32c, returning cached token",
            "2026-04-06T06:59:00Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_3310 latency=38ms",
            "2026-04-06T07:00:01Z WARN  [auth-service] Inbound connection reset by peer (client: api-gateway/10.0.0.15)",
            "2026-04-06T07:00:02Z WARN  [auth-service] Inbound connection reset by peer (client: api-gateway/10.0.0.15)",
            "2026-04-06T07:00:03Z WARN  [auth-service] Inbound connection reset by peer (client: api-gateway/10.0.0.16)",
            "2026-04-06T07:00:04Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_5571 latency=45ms (via surviving connection)",
            "2026-04-06T07:00:05Z INFO  [auth-service] Request processed: POST /auth/token uid=user_7712 latency=40ms (via surviving connection)",
            "2026-04-06T07:00:08Z WARN  [auth-service] Connection pool from api-gateway: 3/10 active (7 reset in last 30s)",
            "2026-04-06T07:00:10Z WARN  [auth-service] Elevated error rate on inbound requests — upstream issue suspected",
            "2026-04-06T07:00:12Z INFO  [auth-service] Internal health check: all subsystems healthy, cache-redis responding normally",
            "2026-04-06T07:00:15Z INFO  [auth-service] Request processed: POST /auth/token uid=user_2209 latency=43ms",
            "2026-04-06T07:00:18Z WARN  [auth-service] Inbound connection reset by peer (client: api-gateway/10.0.0.15)",
            "2026-04-06T07:00:20Z INFO  [auth-service] Note: connection resets are from upstream (api-gateway), not internal errors",
        ],
        "notification-service": [
            "2026-04-06T06:55:00Z INFO  [notification-service] Email batch #5100 sent successfully (12 emails)",
            "2026-04-06T06:58:00Z INFO  [notification-service] Auth token validated for batch #5105 via auth-service (40ms)",
            "2026-04-06T06:58:01Z INFO  [notification-service] Email batch #5105 sent successfully (8 emails)",
            "2026-04-06T07:00:02Z WARN  [notification-service] Auth token validation taking 3200ms — auth-service slow",
            "2026-04-06T07:00:05Z ERROR [notification-service] Auth validation failed for batch #5108 — connection reset by auth-service",
            "2026-04-06T07:00:08Z INFO  [notification-service] Auth validation succeeded for batch #5109 (via cached connection, 45ms)",
            "2026-04-06T07:00:10Z WARN  [notification-service] Queue depth: 1800 — processing stalled on intermittent auth failures",
            "2026-04-06T07:00:12Z ERROR [notification-service] Auth validation failed for batch #5110 — connection reset",
            "2026-04-06T07:00:15Z ERROR [notification-service] 3 consecutive auth validation failures — pausing delivery",
            "2026-04-06T07:00:20Z WARN  [notification-service] Queue depth: 2400 — emails backing up",
        ],
        "user-service": [
            "2026-04-06T07:00:00Z INFO  [user-service] GET /users/profile uid=user_4421 -> 200 (32ms)",
            "2026-04-06T07:00:05Z INFO  [user-service] PUT /users/settings uid=user_3310 -> 200 (78ms)",
            "2026-04-06T07:00:10Z INFO  [user-service] GET /users/profile uid=user_1101 -> 200 (28ms)",
            "2026-04-06T07:00:15Z INFO  [user-service] Health check /healthz -> 200 OK",
        ],
        "payment-service": [
            "2026-04-06T07:00:00Z INFO  [payment-service] Processing payment txn=pay_7701 amount=$55.00 -> db-postgres",
            "2026-04-06T07:00:01Z INFO  [payment-service] Payment completed txn=pay_7701 latency=88ms",
            "2026-04-06T07:00:10Z INFO  [payment-service] Health check /healthz -> 200 OK",
        ],
        "db-postgres": [
            "2026-04-06T07:00:00Z INFO  [db-postgres] Active connections: 38/100",
            "2026-04-06T07:00:05Z INFO  [db-postgres] All queries executing normally. No lock contention.",
            "2026-04-06T07:00:10Z INFO  [db-postgres] Checkpoint starting: time-based",
        ],
        "cache-redis": [
            "2026-04-06T07:00:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T07:00:01Z INFO  [cache-redis] Cache hit ratio: 91%",
            "2026-04-06T07:00:05Z INFO  [cache-redis] Connected clients: 44",
        ],
    },

    metrics={
        "api-gateway": [
            {"timestamp": "2026-04-06T06:55:00Z", "cpu_pct": 20, "mem_pct": 45, "latency_p50": 35, "latency_p99": 90, "error_rate": 0.002, "5xx_rate": 0.001, "tls_handshake_failures": 0},
            {"timestamp": "2026-04-06T07:00:00Z", "cpu_pct": 22, "mem_pct": 46, "latency_p50": 40, "latency_p99": 5200, "error_rate": 0.42, "5xx_rate": 0.40, "tls_handshake_failures": 1560},
            {"timestamp": "2026-04-06T07:00:15Z", "cpu_pct": 23, "mem_pct": 46, "latency_p50": 42, "latency_p99": 5500, "error_rate": 0.48, "5xx_rate": 0.45, "tls_handshake_failures": 2100},
        ],
        "auth-service": [
            {"timestamp": "2026-04-06T06:55:00Z", "cpu_pct": 22, "mem_pct": 58, "latency_p50": 42, "latency_p99": 110, "error_rate": 0.001, "inbound_resets": 0},
            {"timestamp": "2026-04-06T07:00:00Z", "cpu_pct": 20, "mem_pct": 57, "latency_p50": 44, "latency_p99": 120, "error_rate": 0.12, "inbound_resets": 85},
        ],
        "notification-service": [
            {"timestamp": "2026-04-06T06:55:00Z", "cpu_pct": 10, "mem_pct": 28, "queue_depth": 12, "auth_validation_ms": 40, "emails_sent_per_min": 120},
            {"timestamp": "2026-04-06T07:00:00Z", "cpu_pct": 12, "mem_pct": 30, "queue_depth": 1800, "auth_validation_ms": 3200, "emails_sent_per_min": 15},
        ],
    },

    traces={
        "api-gateway": [
            "Trace: POST /api/v2/login (client=10.0.1.52, total=5ms) — FAILED",
            "  ├─ api-gateway.acceptTLS()              FAILED (x509: certificate has expired)",
            "  └─ api-gateway.returnError()              5ms   (502 Bad Gateway)",
            "",
            "Trace: POST /api/v2/login (client=10.0.1.88, total=48ms) — SUCCESS (cached TLS)",
            "  ├─ api-gateway.reuseSession()            2ms   (cached TLS session)",
            "  ├─ api-gateway.routeToAuthService()      42ms  (auth-service -> 200)",
            "  └─ api-gateway.returnResponse()           4ms",
        ],
        "notification-service": [
            "Trace: POST /notifications/send (batch=#5108, total=5200ms) — FAILED",
            "  ├─ notification-service.prepareBatch()     12ms",
            "  ├─ notification-service.validateAuth()     5000ms (-> auth-service connection reset)",
            "  └─ notification-service.sendEmails()       never reached",
        ],
    },

    deploy_history={
        "api-gateway": [
            "v1.12.0  deployed 2026-03-28T09:00:00Z  status=stable  (running 9 days, no recent deploy)",
        ],
        "auth-service": [
            "v2.14.0  deployed 2026-04-01T10:00:00Z  status=stable  (running 5 days)",
        ],
    },

    runbooks={
        "api-gateway": (
            "## api-gateway Runbook\n"
            "- TLS/certificate errors: If logs show 'certificate has expired' or 'x509' errors,\n"
            "  check if cert-manager has renewed the certificate in the Kubernetes secret.\n"
            "  If the secret is updated but the process still has the old cert, restart the service\n"
            "  to reload the certificate from the secret.\n"
            "- 502 errors: Usually caused by downstream service failures OR TLS issues.\n"
            "  If 502s affect ALL routes (not just one downstream), suspect TLS layer.\n"
            "- Circuit breaker open: Downstream service exceeded failure threshold.\n"
            "  Fix the downstream service; breaker auto-closes after 30s healthy."
        ),
        "auth-service": (
            "## auth-service Runbook\n"
            "- Inbound connection resets: If resets are from api-gateway, the issue is upstream,\n"
            "  not in auth-service. Check api-gateway health and TLS status.\n"
            "- High latency: Check cache-redis connectivity.\n"
            "- Internal health check passing but errors on inbound: Upstream is breaking connections."
        ),
        "notification-service": (
            "## notification-service Runbook\n"
            "- Queue backing up: Usually caused by auth-service degradation.\n"
            "  notification-service validates sender auth before sending.\n"
            "  Fix auth-service (or its upstream) first; queue will drain."
        ),
    },

    configs={
        "api-gateway": {
            "current": "TLS_CERT_SECRET=api-gateway-tls\nTLS_MIN_VERSION=1.2\nSESSION_CACHE_SIZE=10000\nSESSION_CACHE_TTL=3600",
            "previous": "TLS_CERT_SECRET=api-gateway-tls\nTLS_MIN_VERSION=1.2\nSESSION_CACHE_SIZE=10000\nSESSION_CACHE_TTL=3600",
            "diff": "No config changes. Certificate was auto-renewed in secret api-gateway-tls by cert-manager at 06:55:00Z, but running process still holds expired cert in memory. Restart required.",
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

    root_cause_services=["api-gateway"],
    root_cause_categories=[RootCauseCategory.CERT_EXPIRY],
    required_fixes=[
        RequiredFix(action="restart_service", service="api-gateway"),
    ],
    diagnosis_keywords=["api-gateway", "certificate", "cert", "TLS", "expired", "expiry", "x509", "handshake", "cert_expiry", "restart"],

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
