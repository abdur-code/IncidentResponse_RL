"""
Scenario schema — shared dataclasses used by all task definitions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models import RootCauseCategory, ServiceStatus


@dataclass
class ServiceConfig:
    """Configuration for a single service in the simulated architecture."""
    status: ServiceStatus
    deps: List[str] = field(default_factory=list)
    version: str = ""
    replicas: int = 1
    is_root_cause: bool = False
    fault_type: Optional[str] = None


@dataclass
class RequiredFix:
    """A fix that the agent must apply to resolve the incident."""
    action: str  # "restart_service", "rollback_deploy", "scale_up"
    service: str
    target_version: Optional[str] = None
    replicas: Optional[int] = None


@dataclass
class IncidentScenario:
    """
    A self-contained incident scenario definition.

    To create a new task, create a new Python file in tasks/ that instantiates
    this dataclass and assigns it to a module-level variable named SCENARIO.
    """
    task_id: str
    name: str
    difficulty: str  # "easy", "medium", "hard"
    max_steps: int
    incident_summary: str

    # Service architecture
    services: Dict[str, ServiceConfig] = field(default_factory=dict)

    # Pre-written data per service
    logs: Dict[str, List[str]] = field(default_factory=dict)
    metrics: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    traces: Dict[str, List[str]] = field(default_factory=dict)
    deploy_history: Dict[str, List[str]] = field(default_factory=dict)
    runbooks: Dict[str, str] = field(default_factory=dict)
    configs: Dict[str, Dict[str, str]] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)

    # Initial alerts
    initial_alerts: List[str] = field(default_factory=list)

    # Ground truth for grading
    root_cause_services: List[str] = field(default_factory=list)
    root_cause_categories: List[RootCauseCategory] = field(default_factory=list)
    required_fixes: List[RequiredFix] = field(default_factory=list)
    diagnosis_keywords: List[str] = field(default_factory=list)
    requires_multi_root_diagnosis: bool = False
    no_fix_score_cap: float = 0.69

    # Grading weights
    weights: Dict[str, float] = field(default_factory=dict)
