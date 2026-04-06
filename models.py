"""
Pydantic models for the SRE Incident Response OpenEnv environment.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class ServiceStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


class ActionType(str, Enum):
    # Investigation (read-only)
    READ_LOGS = "read_logs"
    CHECK_METRICS = "check_metrics"
    PING_SERVICE = "ping_service"
    CHECK_DEPENDENCIES = "check_dependencies"
    INSPECT_DEPLOY = "inspect_deploy"
    QUERY_TRACES = "query_traces"
    CHECK_RUNBOOK = "check_runbook"
    DIFF_CONFIG = "diff_config"

    # Remediation (modifies state)
    RESTART_SERVICE = "restart_service"
    ROLLBACK_DEPLOY = "rollback_deploy"
    SCALE_UP = "scale_up"
    DRAIN_TRAFFIC = "drain_traffic"

    # Terminal
    SUBMIT_DIAGNOSIS = "submit_diagnosis"


class RootCauseCategory(str, Enum):
    OOM_CRASH = "oom_crash"
    DB_DEADLOCK = "db_deadlock"
    BAD_DEPLOY = "bad_deploy"
    MEMORY_LEAK = "memory_leak"
    NETWORK_PARTITION = "network_partition"
    DISK_FULL = "disk_full"
    CONFIG_ERROR = "config_error"
    CERT_EXPIRY = "cert_expiry"
    DNS_FAILURE = "dns_failure"
    RATE_LIMIT = "rate_limit"


INVESTIGATION_ACTIONS = {
    ActionType.READ_LOGS,
    ActionType.CHECK_METRICS,
    ActionType.PING_SERVICE,
    ActionType.CHECK_DEPENDENCIES,
    ActionType.INSPECT_DEPLOY,
    ActionType.QUERY_TRACES,
    ActionType.CHECK_RUNBOOK,
    ActionType.DIFF_CONFIG,
}

REMEDIATION_ACTIONS = {
    ActionType.RESTART_SERVICE,
    ActionType.ROLLBACK_DEPLOY,
    ActionType.SCALE_UP,
    ActionType.DRAIN_TRAFFIC,
}


# ── Action ─────────────────────────────────────────────────────────────

class Action(BaseModel):
    action_type: ActionType
    service: Optional[str] = None
    target_version: Optional[str] = None
    replicas: Optional[int] = Field(None, ge=1, le=10)
    root_cause_service: Optional[str] = None
    root_cause_category: Optional[RootCauseCategory] = None
    fix_description: Optional[str] = None


# ── Observation ────────────────────────────────────────────────────────

class ServiceState(BaseModel):
    status: ServiceStatus
    version: str = ""
    replicas: int = 1


class Observation(BaseModel):
    step_number: int = 0
    timestamp: str = ""
    services: Dict[str, ServiceState] = Field(default_factory=dict)
    active_alerts: List[str] = Field(default_factory=list)
    incident_summary: str = ""
    action_result: Optional[str] = None
    reward: float = 0.0
    done: bool = False
    score: Optional[float] = None
    info: Dict = Field(default_factory=dict)


# ── State ──────────────────────────────────────────────────────────────

class State(BaseModel):
    session_id: str = ""
    task_id: str = ""
    step_count: int = 0
    max_steps: int = 0
    done: bool = False
    actions_taken: List[str] = Field(default_factory=list)
    services_investigated: List[str] = Field(default_factory=list)
    remediations_applied: List[str] = Field(default_factory=list)
    cumulative_reward: float = 0.0


# ── Reward ─────────────────────────────────────────────────────────────

class Reward(BaseModel):
    value: float = Field(0.0, ge=0.0, le=1.0)
    step_reward: float = 0.0
    breakdown: Dict[str, float] = Field(default_factory=dict)
    is_terminal: bool = False


# ── Grader Result ──────────────────────────────────────────────────────

class GraderResult(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    solved: bool = False
    breakdown: Dict[str, float] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)
