"""
Core environment engine — implements reset/step/state for the SRE Incident Response env.
"""

import uuid
import random
from typing import Any, Dict, Optional, Set, Tuple

from models import (
    Action,
    ActionType,
    GraderResult,
    INVESTIGATION_ACTIONS,
    Observation,
    REMEDIATION_ACTIONS,
    RootCauseCategory,
    ServiceState,
    ServiceStatus,
    State,
)
from env.scenario import IncidentScenario, RequiredFix
from tasks import SCENARIOS
from env.services import (
    format_config_diff,
    format_deploy_history,
    format_dependencies,
    format_logs,
    format_metrics,
    format_runbook,
    format_traces,
    generate_alerts,
    ping_service,
    recompute_health,
)


class Session:
    """Tracks the state of a single episode."""

    def __init__(self, scenario: IncidentScenario, session_id: str, seed: int = 0):
        self.session_id = session_id
        self.scenario = scenario
        self.seed = seed
        self.step_count = 0
        self.done = False
        self.cumulative_reward = 0.0

        # Mutable service state: {name: {status, version, replicas}}
        self.services: Dict[str, Dict[str, Any]] = {}
        for name, cfg in scenario.services.items():
            self.services[name] = {
                "status": cfg.status,
                "version": cfg.version,
                "replicas": cfg.replicas,
            }

        # Track which root-cause services have been fixed
        self.fixed_services: Set[str] = set()

        # Build root-cause map: service_name -> fault_type
        self.root_cause_map: Dict[str, str] = {}
        for name, cfg in scenario.services.items():
            if cfg.is_root_cause and cfg.fault_type:
                self.root_cause_map[name] = cfg.fault_type

        # Action history for grading
        self.actions: list[Action] = []
        self.services_investigated: Set[str] = set()
        self.remediations_applied: list[Dict[str, Any]] = []
        self.diagnosis: Optional[Action] = None

        # Seeded evidence ordering (minimal deterministic variation)
        randomizer = random.Random(seed)
        self.logs: Dict[str, list[str]] = {}
        for service_name, log_lines in scenario.logs.items():
            shuffled_logs = list(log_lines)
            randomizer.shuffle(shuffled_logs)
            self.logs[service_name] = shuffled_logs


class IncidentResponseEnv:
    """The SRE Incident Response OpenEnv environment."""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}

    def get_task_ids(self) -> list[str]:
        return list(SCENARIOS.keys())

    def reset(self, task_id: str, seed: int = 0) -> Tuple[Observation, str]:
        """Start a new episode for the given task."""
        if task_id not in SCENARIOS:
            raise ValueError(f"Unknown task_id: {task_id}. Available: {list(SCENARIOS.keys())}")

        scenario = SCENARIOS[task_id]
        session_id = str(uuid.uuid4())[:8]
        session = Session(scenario, session_id, seed=seed)
        self.sessions[session_id] = session

        # Build initial observation
        obs = self._build_observation(session, action_result=None)
        return obs, session_id

    def step(self, session_id: str, action: Action) -> Tuple[Observation, float, bool, Dict]:
        """Execute an action and return (observation, reward, done, info)."""
        session = self._get_session(session_id)
        if session.done:
            obs = self._build_observation(session, action_result="Episode already finished.")
            return obs, 0.0, True, {"error": "Episode already finished."}

        session.step_count += 1
        session.actions.append(action)

        reward = 0.0
        action_result = ""
        info: Dict[str, Any] = {}

        service_name = action.service
        scenario = session.scenario

        # Validate service name for actions that require it
        if action.action_type != ActionType.SUBMIT_DIAGNOSIS:
            if service_name and service_name not in scenario.services:
                action_result = f"Unknown service: '{service_name}'. Available: {list(scenario.services.keys())}"
                obs = self._build_observation(session, action_result=action_result)
                return obs, 0.0, False, {"error": action_result}
            if not service_name and action.action_type != ActionType.SUBMIT_DIAGNOSIS:
                action_result = "Action requires a 'service' parameter."
                obs = self._build_observation(session, action_result=action_result)
                return obs, 0.0, False, {"error": action_result}

        # ── Investigation actions ──
        if action.action_type in INVESTIGATION_ACTIONS:
            session.services_investigated.add(service_name)
            action_result = self._handle_investigation(session, action)

            # Small reward for investigating root cause services
            if service_name in scenario.root_cause_services:
                reward = 0.01
            else:
                reward = 0.0

        # ── Remediation actions ──
        elif action.action_type in REMEDIATION_ACTIONS:
            action_result, reward = self._handle_remediation(session, action)
            remediation_record = {
                "action": action.action_type.value,
                "service": service_name,
                "target_version": action.target_version,
                "replicas": action.replicas,
            }
            session.remediations_applied.append(remediation_record)

        # ── Submit diagnosis ──
        elif action.action_type == ActionType.SUBMIT_DIAGNOSIS:
            session.diagnosis = action
            session.done = True
            grader_result = self._grade(session)
            reward = grader_result.score
            action_result = f"Diagnosis submitted. Score: {grader_result.score:.2f}"
            info["grader_result"] = grader_result.model_dump()

        session.cumulative_reward += reward

        # Check max steps
        if session.step_count >= scenario.max_steps and not session.done:
            session.done = True
            if session.diagnosis is None:
                # Auto-grade with whatever we have
                grader_result = self._grade(session)
                reward = grader_result.score
                info["grader_result"] = grader_result.model_dump()
                action_result += f"\n[MAX STEPS REACHED] Episode ended. Score: {grader_result.score:.2f}"

        obs = self._build_observation(session, action_result=action_result, reward=reward)
        obs.done = session.done
        if "grader_result" in info:
            obs.score = info["grader_result"]["score"]

        return obs, reward, session.done, info

    def state(self, session_id: str) -> State:
        """Return current episode state."""
        session = self._get_session(session_id)
        return State(
            session_id=session.session_id,
            task_id=session.scenario.task_id,
            step_count=session.step_count,
            max_steps=session.scenario.max_steps,
            done=session.done,
            actions_taken=[a.action_type.value for a in session.actions],
            services_investigated=list(session.services_investigated),
            remediations_applied=[f"{r['action']}({r['service']})" for r in session.remediations_applied],
            cumulative_reward=round(session.cumulative_reward, 4),
        )

    # ── Internal helpers ───────────────────────────────────────────────

    def _get_session(self, session_id: str) -> Session:
        if session_id not in self.sessions:
            raise ValueError(f"Unknown session: {session_id}")
        return self.sessions[session_id]

    def _build_observation(
        self, session: Session, action_result: Optional[str], reward: float = 0.0,
    ) -> Observation:
        scenario = session.scenario
        svc_states = {}
        for name, data in session.services.items():
            svc_states[name] = ServiceState(
                status=data["status"],
                version=data["version"],
                replicas=data["replicas"],
            )

        alerts = generate_alerts(
            session.services, scenario.initial_alerts, session.fixed_services,
        )

        return Observation(
            step_number=session.step_count,
            timestamp=f"2026-04-06T04:{session.step_count:02d}:00Z",
            services=svc_states,
            active_alerts=alerts,
            incident_summary=scenario.incident_summary if session.step_count == 0 else "",
            action_result=action_result,
            reward=round(reward, 4),
            done=session.done,
        )

    def _handle_investigation(self, session: Session, action: Action) -> str:
        scenario = session.scenario
        svc = action.service

        if action.action_type == ActionType.READ_LOGS:
            logs = session.logs.get(svc, [])
            return format_logs(logs)

        elif action.action_type == ActionType.CHECK_METRICS:
            metrics = scenario.metrics.get(svc, [])
            return format_metrics(metrics)

        elif action.action_type == ActionType.PING_SERVICE:
            status = session.services[svc]["status"]
            return ping_service(status, svc)

        elif action.action_type == ActionType.CHECK_DEPENDENCIES:
            deps = scenario.dependencies.get(svc, [])
            dep_info = format_dependencies(deps)
            # Also show current health of dependencies
            dep_health = []
            for d in deps:
                if d in session.services:
                    dep_health.append(f"  {d}: {session.services[d]['status'].value}")
            if dep_health:
                dep_info += "\n\nDependency health:\n" + "\n".join(dep_health)
            return dep_info

        elif action.action_type == ActionType.INSPECT_DEPLOY:
            deploys = scenario.deploy_history.get(svc, [])
            return format_deploy_history(deploys)

        elif action.action_type == ActionType.QUERY_TRACES:
            traces = scenario.traces.get(svc, [])
            return format_traces(traces)

        elif action.action_type == ActionType.CHECK_RUNBOOK:
            runbook = scenario.runbooks.get(svc, "")
            return format_runbook(runbook)

        elif action.action_type == ActionType.DIFF_CONFIG:
            configs = scenario.configs.get(svc, {})
            return format_config_diff(configs)

        return f"No data available for {action.action_type.value} on {svc}."

    def _handle_remediation(self, session: Session, action: Action) -> Tuple[str, float]:
        scenario = session.scenario
        svc = action.service
        reward = 0.0
        result = ""

        # Check if this remediation matches any required fix
        fix_matched = False
        for req_fix in scenario.required_fixes:
            if self._fix_matches(action, req_fix):
                fix_matched = True
                session.fixed_services.add(svc)
                reward = 0.05
                break

        if action.action_type == ActionType.RESTART_SERVICE:
            if fix_matched:
                session.services[svc]["status"] = ServiceStatus.HEALTHY
                result = f"Service '{svc}' restarted successfully. Status: HEALTHY"
            else:
                # Restarting a non-root-cause service: no effect on the underlying issue
                current = session.services[svc]["status"]
                if current == ServiceStatus.DOWN and svc in session.root_cause_map:
                    result = f"Service '{svc}' restarted but crashed again — underlying issue persists."
                elif current == ServiceStatus.HEALTHY:
                    result = f"Service '{svc}' restarted. It was already healthy — no change."
                else:
                    result = f"Service '{svc}' restarted. Status unchanged — issue is caused by an upstream dependency."
                reward = -0.05

        elif action.action_type == ActionType.ROLLBACK_DEPLOY:
            if fix_matched:
                session.services[svc]["version"] = action.target_version or ""
                session.services[svc]["status"] = ServiceStatus.HEALTHY
                result = (
                    f"Service '{svc}' rolled back to {action.target_version}. "
                    f"Pods restarting with previous version... Status: HEALTHY"
                )
            else:
                current_version = session.services[svc]["version"]
                result = (
                    f"Rolled back '{svc}' to {action.target_version}, but this didn't resolve the issue. "
                    f"Previous version was {current_version}."
                )
                reward = -0.05

        elif action.action_type == ActionType.SCALE_UP:
            replicas = action.replicas or 3
            if fix_matched:
                session.services[svc]["replicas"] = replicas
                session.services[svc]["status"] = ServiceStatus.HEALTHY
                result = f"Service '{svc}' scaled to {replicas} replicas. Memory pressure alleviated. Status: HEALTHY"
                reward = 0.05
            else:
                session.services[svc]["replicas"] = replicas
                result = f"Service '{svc}' scaled to {replicas} replicas. No effect on the underlying issue."
                reward = -0.05

        # Recompute health after remediation
        session.services = recompute_health(
            session.services,
            scenario.dependencies,
            session.fixed_services,
            session.root_cause_map,
        )

        # Add post-remediation status summary
        still_broken = [
            name for name, data in session.services.items()
            if data["status"] != ServiceStatus.HEALTHY
        ]
        if still_broken:
            result += f"\n\n[POST-REMEDIATION CHECK] Services still unhealthy: {', '.join(still_broken)}"
        else:
            result += "\n\n[POST-REMEDIATION CHECK] All services are now HEALTHY."

        return result, reward

    def _fix_matches(self, action: Action, req_fix: RequiredFix) -> bool:
        """Check if an action matches a required fix."""
        if action.action_type.value != req_fix.action:
            return False
        if action.service != req_fix.service:
            return False
        if req_fix.target_version and action.target_version != req_fix.target_version:
            return False
        if req_fix.replicas is not None and action.replicas != req_fix.replicas:
            return False
        return True

    def _grade(self, session: Session) -> GraderResult:
        """Deterministic grading of the episode."""
        from graders.grader import grade_episode
        return grade_episode(session)
