"""
Task: Notification Service DNS Resolution Failure
SMTP relay provider changed IP addresses. notification-service has a stale DNS cache
and cannot resolve the relay hostname. Only notification-service is affected — it's
a leaf node with no downstream dependents.
"""

from env.scenario import IncidentScenario, RequiredFix, ServiceConfig
from models import RootCauseCategory, ServiceStatus


SCENARIO = IncidentScenario(
    task_id="easy_dns",
    name="Notification Service DNS Failure",
    difficulty="easy",
    max_steps=15,
    incident_summary=(
        "Alert at 06:00 UTC. notification-service is failing to deliver emails. "
        "SMTP connections timing out with DNS resolution errors. All other services "
        "are operating normally. Customer impact: password reset emails and order "
        "confirmation emails are not being delivered."
    ),

    services={
        "api-gateway": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=["auth-service", "user-service", "payment-service"],
            version="v1.12.0", replicas=3,
        ),
        "auth-service": ServiceConfig(
            status=ServiceStatus.HEALTHY, deps=["cache-redis"],
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
            status=ServiceStatus.DOWN, deps=["auth-service"],
            version="v1.5.0", replicas=1, is_root_cause=True, fault_type="dns_failure",
        ),
    },

    initial_alerts=[
        "[ALERT SEV-2] notification-service: email delivery failing, SMTP connection errors",
        "[ALERT SEV-3] notification-service: health check failing on external dependency (SMTP relay)",
    ],

    logs={
        "notification-service": [
            "2026-04-06T05:45:00Z INFO  [notification-service] Email batch #5001 sent successfully (18 emails)",
            "2026-04-06T05:45:05Z INFO  [notification-service] Auth token validated for batch #5002 via auth-service (42ms)",
            "2026-04-06T05:45:06Z INFO  [notification-service] Email batch #5002 sent successfully (11 emails)",
            "2026-04-06T05:50:00Z INFO  [notification-service] Email batch #5005 sent successfully (9 emails)",
            "2026-04-06T05:50:05Z INFO  [notification-service] SMTP relay: smtp-relay.mailprovider.net resolved to 198.51.100.22",
            "2026-04-06T05:50:06Z INFO  [notification-service] Connection to SMTP relay established in 45ms",
            "2026-04-06T05:55:00Z INFO  [notification-service] Email batch #5008 sent successfully (15 emails)",
            "2026-04-06T05:55:02Z INFO  [notification-service] Auth token validated for batch #5009 via auth-service (38ms)",
            "2026-04-06T05:55:03Z INFO  [notification-service] Email batch #5009 sent successfully (7 emails)",
            "2026-04-06T06:00:00Z ERROR [notification-service] DNS resolution failed: getaddrinfo ENOTFOUND smtp-relay.mailprovider.net",
            "2026-04-06T06:00:01Z ERROR [notification-service] SMTP connection failed: could not resolve hostname smtp-relay.mailprovider.net",
            "2026-04-06T06:00:02Z ERROR [notification-service] Email delivery failed for batch #5010: SMTP transport error — DNS_RESOLUTION_FAILED",
            "2026-04-06T06:00:03Z WARN  [notification-service] Queuing 22 emails for retry. Queue depth: 22",
            "2026-04-06T06:00:05Z WARN  [notification-service] Retrying SMTP connection (attempt 2/3)...",
            "2026-04-06T06:00:08Z ERROR [notification-service] DNS resolution failed: getaddrinfo ENOTFOUND smtp-relay.mailprovider.net (retry 2)",
            "2026-04-06T06:00:10Z WARN  [notification-service] Retrying SMTP connection (attempt 3/3)...",
            "2026-04-06T06:00:13Z ERROR [notification-service] DNS resolution failed: getaddrinfo ENOTFOUND smtp-relay.mailprovider.net (retry 3)",
            "2026-04-06T06:00:14Z ERROR [notification-service] SMTP connection failed after 3 retries — all attempts exhausted",
            "2026-04-06T06:00:15Z ERROR [notification-service] Marking SMTP relay as unreachable. Will not attempt new connections.",
            "2026-04-06T06:00:16Z ERROR [notification-service] Health check /healthz returning 503: critical dependency smtp-relay unreachable",
            "2026-04-06T06:00:20Z WARN  [notification-service] Email queue depth: 85 (growing — no delivery possible)",
            "2026-04-06T06:00:30Z WARN  [notification-service] Email queue depth: 180",
            "2026-04-06T06:01:00Z WARN  [notification-service] Email queue depth: 350",
            "2026-04-06T06:02:00Z ERROR [notification-service] Email queue depth: 450 — approaching queue limit (1000)",
        ],
        "auth-service": [
            "2026-04-06T06:00:00Z INFO  [auth-service] Request processed: POST /auth/token uid=user_8832 latency=45ms",
            "2026-04-06T06:00:05Z INFO  [auth-service] Cache hit for session sid=a8f32c, returning cached token",
            "2026-04-06T06:00:10Z INFO  [auth-service] Request processed: POST /auth/verify uid=user_3310 latency=38ms",
            "2026-04-06T06:00:15Z INFO  [auth-service] Health check /healthz -> 200 OK",
        ],
        "api-gateway": [
            "2026-04-06T06:00:00Z INFO  [api-gateway] Route: POST /api/v2/login -> auth-service (200, 45ms)",
            "2026-04-06T06:00:02Z INFO  [api-gateway] Route: GET /api/v2/user/profile -> user-service (200, 30ms)",
            "2026-04-06T06:00:05Z INFO  [api-gateway] Route: POST /api/v2/pay -> payment-service (200, 88ms)",
            "2026-04-06T06:00:10Z INFO  [api-gateway] All downstream services healthy.",
        ],
        "user-service": [
            "2026-04-06T06:00:00Z INFO  [user-service] GET /users/profile uid=user_4421 -> 200 (32ms)",
            "2026-04-06T06:00:05Z INFO  [user-service] PUT /users/settings uid=user_3310 -> 200 (78ms)",
            "2026-04-06T06:00:10Z INFO  [user-service] Health check /healthz -> 200 OK",
        ],
        "payment-service": [
            "2026-04-06T06:00:00Z INFO  [payment-service] Processing payment txn=pay_6601 amount=$55.00 -> db-postgres",
            "2026-04-06T06:00:01Z INFO  [payment-service] Payment completed txn=pay_6601 latency=85ms",
            "2026-04-06T06:00:10Z INFO  [payment-service] Health check /healthz -> 200 OK",
        ],
        "db-postgres": [
            "2026-04-06T06:00:00Z INFO  [db-postgres] Active connections: 38/100",
            "2026-04-06T06:00:02Z INFO  [db-postgres] Checkpoint starting: time-based",
            "2026-04-06T06:00:04Z INFO  [db-postgres] Checkpoint complete: wrote 850 buffers (5.8%)",
        ],
        "cache-redis": [
            "2026-04-06T06:00:00Z INFO  [cache-redis] Memory usage: 1.2GB/4.0GB (30%)",
            "2026-04-06T06:00:01Z INFO  [cache-redis] Cache hit ratio: 92%",
            "2026-04-06T06:00:05Z INFO  [cache-redis] Connected clients: 45",
        ],
    },

    metrics={
        "notification-service": [
            {"timestamp": "2026-04-06T05:45:00Z", "cpu_pct": 10, "mem_pct": 28, "emails_sent_per_min": 120, "smtp_connect_ms": 45, "dns_resolve_ms": 2, "queue_depth": 5},
            {"timestamp": "2026-04-06T05:55:00Z", "cpu_pct": 10, "mem_pct": 28, "emails_sent_per_min": 115, "smtp_connect_ms": 48, "dns_resolve_ms": 3, "queue_depth": 8},
            {"timestamp": "2026-04-06T06:00:00Z", "cpu_pct": 8, "mem_pct": 27, "emails_sent_per_min": 0, "smtp_connect_ms": "timeout", "dns_resolve_ms": "timeout", "queue_depth": 450},
        ],
    },

    traces={
        "notification-service": [
            "Trace: POST /notifications/send (batch=#5010, total=3200ms) — FAILED",
            "  ├─ notification-service.prepareBatch()     8ms",
            "  ├─ notification-service.validateAuth()     42ms  (auth-service -> 200 OK)",
            "  ├─ notification-service.resolveSMTP()      3000ms (DNS lookup TIMEOUT — ENOTFOUND)",
            "  └─ notification-service.sendEmails()       never reached",
        ],
    },

    deploy_history={
        "notification-service": [
            "v1.5.0  deployed 2026-04-02T12:00:00Z  status=stable  (running 4 days until DNS failure)",
            "v1.4.2  deployed 2026-03-20T09:00:00Z  status=superseded",
        ],
    },

    runbooks={
        "notification-service": (
            "## notification-service Runbook\n"
            "- DNS resolution failures: The service caches DNS lookups for SMTP relay hostnames.\n"
            "  If the relay provider changes IPs, the stale cache causes ENOTFOUND errors.\n"
            "  Fix: restart the service to flush the internal DNS cache and force re-resolution.\n"
            "- SMTP connection failures: Check if the relay is reachable from the pod network.\n"
            "  Also check if SMTP credentials have expired.\n"
            "- Queue growing: Usually caused by SMTP delivery failures. Fix the SMTP connection\n"
            "  first; the queue will drain automatically once delivery resumes."
        ),
    },

    configs={
        "notification-service": {
            "current": "SMTP_HOST=smtp-relay.mailprovider.net\nSMTP_PORT=587\nSMTP_TLS=true\nDNS_CACHE_TTL=3600\nQUEUE_MAX_SIZE=1000",
            "previous": "SMTP_HOST=smtp-relay.mailprovider.net\nSMTP_PORT=587\nSMTP_TLS=true\nDNS_CACHE_TTL=3600\nQUEUE_MAX_SIZE=1000",
            "diff": "No changes — config has not been modified recently. DNS cache TTL is 3600s (1 hour), which caused stale resolution after provider IP change.",
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

    root_cause_services=["notification-service"],
    root_cause_categories=[RootCauseCategory.DNS_FAILURE],
    required_fixes=[
        RequiredFix(action="restart_service", service="notification-service"),
    ],
    diagnosis_keywords=["notification-service", "dns", "DNS", "resolution", "smtp", "ENOTFOUND", "hostname", "dns_failure"],

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
