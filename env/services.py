"""
Service simulation helpers — generates alerts, formats data, cascades dependency health.
"""

import datetime as dt
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from models import ServiceStatus


def generate_alerts(
    services: Dict[str, Any],
    scenario_alerts: List[str],
    fixed_services: Set[str],
) -> List[str]:
    """Merge scenario-authored and dynamic alerts using deterministic ordering."""
    dynamic_alerts: List[str] = []
    for svc_name, svc in services.items():
        status = svc["status"]
        if status == ServiceStatus.DOWN and svc_name not in fixed_services:
            dynamic_alerts.append(f"[ALERT SEV-1] {svc_name}: service is DOWN, 0 healthy pods")
        elif status == ServiceStatus.DEGRADED and svc_name not in fixed_services:
            dynamic_alerts.append(f"[ALERT SEV-2] {svc_name}: service is DEGRADED")

    filtered_scenario_alerts: List[str] = []
    for alert in scenario_alerts:
        _, service_name, _ = _parse_alert_metadata(alert)
        if service_name and service_name in services:
            svc_status = services[service_name]["status"]
            if svc_status == ServiceStatus.HEALTHY or service_name in fixed_services:
                continue
        filtered_scenario_alerts.append(alert)

    combined_alerts = filtered_scenario_alerts + dynamic_alerts
    deduped: List[str] = []
    seen_keys = set()
    for alert in combined_alerts:
        key = _alert_dedupe_key(alert)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(alert)
    deduped.sort(key=_alert_sort_key)

    if not deduped:
        return ["[INFO] All services HEALTHY — no active alerts."]
    return deduped


def _parse_alert_metadata(alert: str) -> Tuple[int, Optional[str], Optional[dt.datetime]]:
    severity_rank = 4
    if "SEV-1" in alert:
        severity_rank = 1
    elif "SEV-2" in alert:
        severity_rank = 2
    elif "SEV-3" in alert:
        severity_rank = 3

    service_name: Optional[str] = None
    service_match = re.search(r"\] ([a-z0-9-]+):", alert)
    if service_match:
        service_name = service_match.group(1)

    timestamp: Optional[dt.datetime] = None
    timestamp_match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", alert)
    if timestamp_match:
        timestamp = dt.datetime.fromisoformat(timestamp_match.group(0).replace("Z", "+00:00"))

    return severity_rank, service_name, timestamp


def _alert_dedupe_key(alert: str) -> Tuple[str, str, str]:
    severity_rank, service_name, _ = _parse_alert_metadata(alert)
    severity = f"SEV-{severity_rank}" if severity_rank < 4 else "INFO"

    message = alert
    if service_name and f"{service_name}:" in alert:
        message = alert.split(f"{service_name}:", 1)[1].strip()
    message = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", "", message).strip()

    return (severity, service_name or "", message)


def _alert_sort_key(alert: str) -> Tuple[int, str, str]:
    severity_rank, service_name, timestamp = _parse_alert_metadata(alert)
    service_sort = service_name or "zzzzzz"
    timestamp_sort = timestamp.isoformat() if timestamp else "9999-12-31T23:59:59+00:00"
    return (severity_rank, service_sort, timestamp_sort)


def recompute_health(
    services: Dict[str, Any],
    dependencies: Dict[str, List[str]],
    fixed_services: Set[str],
    root_cause_map: Dict[str, str],
) -> Dict[str, Any]:
    """Walk the dependency graph and update service health.

    Rules:
    - A root-cause service that has been fixed becomes HEALTHY.
    - A non-root-cause service becomes HEALTHY if all its deps are HEALTHY.
    - A non-root-cause service becomes DEGRADED if any dep is DEGRADED.
    - A non-root-cause service becomes DOWN if any dep is DOWN.
    """
    updated = {k: dict(v) for k, v in services.items()}

    # First, fix root-cause services that have been remediated
    for svc_name in fixed_services:
        if svc_name in updated:
            updated[svc_name]["status"] = ServiceStatus.HEALTHY

    # Iteratively propagate health (max 5 rounds to handle chains)
    for _ in range(5):
        changed = False
        for svc_name, deps in dependencies.items():
            if svc_name in fixed_services:
                continue
            if svc_name in root_cause_map and svc_name not in fixed_services:
                continue  # still broken

            if not deps:
                continue

            dep_statuses = [updated[d]["status"] for d in deps if d in updated]
            if not dep_statuses:
                continue

            if any(s == ServiceStatus.DOWN for s in dep_statuses):
                new_status = ServiceStatus.DEGRADED  # downstream of DOWN = DEGRADED
            elif any(s == ServiceStatus.DEGRADED for s in dep_statuses):
                new_status = ServiceStatus.DEGRADED
            else:
                new_status = ServiceStatus.HEALTHY

            if updated[svc_name]["status"] != new_status:
                updated[svc_name]["status"] = new_status
                changed = True

        if not changed:
            break

    return updated


def format_metrics(metrics_list: List[Dict[str, Any]]) -> str:
    """Format time-series metrics into a readable table."""
    if not metrics_list:
        return "No metrics available for this service."

    # Get all keys from the first entry
    keys = list(metrics_list[0].keys())
    header = "  ".join(f"{k:<18}" for k in keys)
    lines = [header, "-" * len(header)]
    for row in metrics_list:
        vals = []
        for k in keys:
            v = row.get(k, "")
            vals.append(f"{str(v):<18}")
        lines.append("  ".join(vals))
    return "\n".join(lines)


def format_logs(log_lines: List[str]) -> str:
    """Join log lines with newlines."""
    if not log_lines:
        return "No logs available for this service."
    return "\n".join(log_lines)


def format_traces(trace_lines: List[str]) -> str:
    """Format trace data."""
    if not trace_lines:
        return "No traces available for this service."
    return "\n".join(trace_lines)


def format_deploy_history(deploy_lines: List[str]) -> str:
    """Format deploy history."""
    if not deploy_lines:
        return "No deploy history available for this service."
    return "\n".join(deploy_lines)


def format_dependencies(deps: List[str]) -> str:
    """Format dependency list."""
    if not deps:
        return "This service has no upstream dependencies."
    return "Dependencies: " + ", ".join(deps)


def format_runbook(runbook: str) -> str:
    """Return runbook text."""
    if not runbook:
        return "No runbook available for this service."
    return runbook


def format_config_diff(config_data: Dict[str, str]) -> str:
    """Format config diff."""
    if not config_data:
        return "No config data available for this service."
    result = []
    if "diff" in config_data:
        result.append(f"Config diff: {config_data['diff']}")
    if "current" in config_data:
        result.append(f"\nCurrent config:\n{config_data['current']}")
    return "\n".join(result)


def ping_service(status: ServiceStatus, service_name: str) -> str:
    """Simulate a ping to a service."""
    if status == ServiceStatus.HEALTHY:
        return f"PING {service_name}: responding on :8080/healthz — 200 OK (latency: 5ms)"
    elif status == ServiceStatus.DEGRADED:
        return f"PING {service_name}: responding on :8080/healthz — 200 OK (latency: 1200ms, SLOW)"
    else:
        return f"PING {service_name}: connection refused on :8080/healthz — service unreachable"
