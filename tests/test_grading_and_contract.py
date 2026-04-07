from fastapi.testclient import TestClient

from env.environment import IncidentResponseEnv
from env.scenario import RequiredFix
from env.services import generate_alerts
from models import Action, ActionType, RootCauseCategory, ServiceStatus
from server.app import app


def _submit(env: IncidentResponseEnv, session_id: str, action: Action):
    return env.step(session_id, action)


def _hard_fix_actions():
    return [
        Action(
            action_type=ActionType.ROLLBACK_DEPLOY,
            service="payment-service",
            target_version="v3.8.1",
        ),
        Action(
            action_type=ActionType.RESTART_SERVICE,
            service="cache-redis",
        ),
    ]


def test_multi_root_partial_credit_after_required_fixes():
    env = IncidentResponseEnv()

    obs_one, sid_one = env.reset("hard", seed=7)
    for fix_action in _hard_fix_actions():
        _submit(env, sid_one, fix_action)
    obs_one, reward_one, done_one, info_one = _submit(
        env,
        sid_one,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_services=["payment-service"],
            root_cause_categories=[RootCauseCategory.BAD_DEPLOY],
            fix_description="Rolled back payment-service and restarted cache-redis",
        ),
    )

    obs_two, sid_two = env.reset("hard", seed=7)
    for fix_action in _hard_fix_actions():
        _submit(env, sid_two, fix_action)
    obs_two, reward_two, done_two, info_two = _submit(
        env,
        sid_two,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_services=["payment-service", "cache-redis"],
            root_cause_categories=[RootCauseCategory.BAD_DEPLOY, RootCauseCategory.MEMORY_LEAK],
            fix_description="Rolled back payment-service and restarted cache-redis",
        ),
    )

    score_one = info_one["grader_result"]["score"]
    score_two = info_two["grader_result"]["score"]

    assert done_one and done_two
    assert score_two > score_one


def test_required_fixes_are_order_independent_and_set_based():
    env = IncidentResponseEnv()

    obs_forward, sid_forward = env.reset("hard", seed=9)
    for fix_action in _hard_fix_actions():
        _submit(env, sid_forward, fix_action)
    obs_forward, reward_forward, done_forward, info_forward = _submit(
        env,
        sid_forward,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_services=["payment-service", "cache-redis"],
            root_cause_categories=[RootCauseCategory.BAD_DEPLOY, RootCauseCategory.MEMORY_LEAK],
            fix_description="Rolled back payment-service and restarted cache-redis",
        ),
    )

    obs_reverse, sid_reverse = env.reset("hard", seed=9)
    for fix_action in reversed(_hard_fix_actions()):
        _submit(env, sid_reverse, fix_action)
    obs_reverse, reward_reverse, done_reverse, info_reverse = _submit(
        env,
        sid_reverse,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_services=["payment-service", "cache-redis"],
            root_cause_categories=[RootCauseCategory.BAD_DEPLOY, RootCauseCategory.MEMORY_LEAK],
            fix_description="Rolled back payment-service and restarted cache-redis",
        ),
    )

    breakdown_forward = info_forward["grader_result"]["breakdown"]
    breakdown_reverse = info_reverse["grader_result"]["breakdown"]

    assert done_forward and done_reverse
    assert breakdown_forward["correct_fix"] == breakdown_reverse["correct_fix"]
    assert breakdown_forward["secondary_fix"] == breakdown_reverse["secondary_fix"]


def test_no_fix_penalty_cap_applies():
    env = IncidentResponseEnv()

    obs, sid = env.reset("easy", seed=3)
    obs, reward, done, info = _submit(
        env,
        sid,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_service="auth-service",
            root_cause_category=RootCauseCategory.OOM_CRASH,
            fix_description="Auth service had OOM crash and needed restart",
        ),
    )

    score = info["grader_result"]["score"]
    assert done
    assert score <= 0.69


def test_partial_fix_increases_no_fix_cap_proportionally():
    env = IncidentResponseEnv()

    obs_none, sid_none = env.reset("hard", seed=4)
    obs_none, reward_none, done_none, info_none = _submit(
        env,
        sid_none,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_services=["payment-service", "cache-redis"],
            root_cause_categories=[RootCauseCategory.BAD_DEPLOY, RootCauseCategory.MEMORY_LEAK],
            fix_description="Payment bad deploy and cache memory leak",
        ),
    )

    obs_partial, sid_partial = env.reset("hard", seed=4)
    _submit(
        env,
        sid_partial,
        Action(
            action_type=ActionType.RESTART_SERVICE,
            service="cache-redis",
        ),
    )
    obs_partial, reward_partial, done_partial, info_partial = _submit(
        env,
        sid_partial,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_services=["payment-service", "cache-redis"],
            root_cause_categories=[RootCauseCategory.BAD_DEPLOY, RootCauseCategory.MEMORY_LEAK],
            fix_description="Payment bad deploy and cache memory leak",
        ),
    )

    score_none = info_none["grader_result"]["score"]
    score_partial = info_partial["grader_result"]["score"]

    assert done_none and done_partial
    assert score_partial > score_none


def test_required_fix_matching_normalizes_case_and_ignores_irrelevant_fields():
    env = IncidentResponseEnv()

    obs, sid = env.reset("hard", seed=12)
    env.sessions[sid].remediations_applied.append(
        {
            "action": "RESTART_SERVICE",
            "service": "CACHE-REDIS",
            "target_version": None,
            "replicas": None,
            "noise": "ignored",
        }
    )

    obs, reward, done, info = _submit(
        env,
        sid,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_services=["payment-service", "cache-redis"],
            root_cause_categories=[RootCauseCategory.BAD_DEPLOY, RootCauseCategory.MEMORY_LEAK],
            fix_description="Handled both incidents",
        ),
    )

    breakdown = info["grader_result"]["breakdown"]
    assert done
    assert breakdown["correct_fix"] > 0.0


def test_scale_up_default_replicas_matches_required_fix_of_three():
    env = IncidentResponseEnv()

    obs, sid = env.reset("easy", seed=11)
    scenario = env.sessions[sid].scenario
    original_required_fixes = list(scenario.required_fixes)
    scenario.required_fixes = [
        RequiredFix(action="scale_up", service="auth-service", replicas=3)
    ]

    try:
        obs, reward, done, info = _submit(
            env,
            sid,
            Action(
                action_type=ActionType.SCALE_UP,
                service="auth-service",
            ),
        )

        assert reward == 0.05
        assert env.sessions[sid].remediations_applied[-1]["replicas"] == 3
    finally:
        scenario.required_fixes = original_required_fixes


def test_singular_and_plural_diagnosis_fields_do_not_double_count():
    env = IncidentResponseEnv()

    obs, sid = env.reset("easy", seed=5)
    _submit(
        env,
        sid,
        Action(
            action_type=ActionType.RESTART_SERVICE,
            service="auth-service",
        ),
    )
    obs, reward, done, info = _submit(
        env,
        sid,
        Action(
            action_type=ActionType.SUBMIT_DIAGNOSIS,
            root_cause_service="auth-service",
            root_cause_services=["auth-service"],
            root_cause_category=RootCauseCategory.OOM_CRASH,
            root_cause_categories=[RootCauseCategory.OOM_CRASH],
            fix_description="Auth OOM resolved by restart",
        ),
    )

    breakdown = info["grader_result"]["breakdown"]
    assert done
    assert breakdown["correct_service"] <= 0.30
    assert breakdown["correct_category"] <= 0.20


def test_alert_merge_is_deterministic_by_severity_service_timestamp():
    services = {
        "api-gateway": {"status": ServiceStatus.DEGRADED},
        "payment-service": {"status": ServiceStatus.DOWN},
        "auth-service": {"status": ServiceStatus.DEGRADED},
    }
    scenario_alerts = [
        "[ALERT SEV-2] auth-service: intermittent timeouts",
        "[ALERT SEV-1] payment-service: health checks failing",
        "[ALERT SEV-3] api-gateway: elevated latency",
    ]

    alerts = generate_alerts(services, scenario_alerts, fixed_services=set())

    sev_levels = [
        1 if "SEV-1" in alert else 2 if "SEV-2" in alert else 3 if "SEV-3" in alert else 4
        for alert in alerts
    ]
    assert sev_levels == sorted(sev_levels)

    sev2_alerts = [alert for alert in alerts if "SEV-2" in alert]
    sev2_services = [alert.split("] ", 1)[1].split(":", 1)[0] for alert in sev2_alerts]
    assert sev2_services == sorted(sev2_services)


def test_alert_dedupe_ignores_timestamp_for_same_semantic_message():
    services = {
        "payment-service": {"status": ServiceStatus.DOWN},
    }
    scenario_alerts = [
        "[ALERT SEV-1] payment-service: 2026-04-07T01:00:00Z health checks failing",
        "[ALERT SEV-1] payment-service: 2026-04-07T01:01:00Z health checks failing",
    ]

    alerts = generate_alerts(services, scenario_alerts, fixed_services=set())
    semantically_same = [
        alert for alert in alerts
        if "SEV-1" in alert and "payment-service" in alert and "health checks failing" in alert
    ]

    assert len(semantically_same) == 1


def test_state_endpoint_requires_session_id():
    client = TestClient(app)
    response = client.get("/state")
    assert response.status_code == 404
