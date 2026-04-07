"""
Inference Script — SRE Incident Response Environment
=====================================================
MANDATORY:
- Before submitting, ensure the following variables are defined in your environment:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    LOCAL_IMAGE_NAME  The name of the local Docker image (if using from_docker_image)

- The inference script must be named `inference.py` and placed in the root directory
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import asyncio
import json
import os
import sys
import textwrap
from typing import List

from openai import OpenAI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Action, ActionType, RootCauseCategory
from env.environment import IncidentResponseEnv

IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
BENCHMARK = "sre_incident_response"
MAX_STEPS = 20
TEMPERATURE = 0.7
SUCCESS_SCORE_THRESHOLD = 0.7


# ── Logging helpers (strict format) ───────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error) -> None:
    error_str = str(error) if error is not None else "null"
    done_str = "true" if done else "false"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_str} error={error_str}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    success_str = "true" if success else "false"
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={success_str} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ── System prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""\
You are an expert SRE (Site Reliability Engineer) responding to a production incident.
You are given the current state of a microservice architecture and must:
1. Investigate by reading logs, checking metrics, tracing requests, and examining dependencies
2. Identify the root cause(s)
3. Apply the correct fix(es)
4. Submit a diagnosis

CRITICAL CONSTRAINT:
- Do not submit diagnosis until all alerts are resolved and all services are HEALTHY.

Available actions (respond with a single JSON object):

Investigation actions (require "service" field):
- read_logs: Read recent logs from a service
- check_metrics: Get time-series metrics (CPU, memory, latency, error rate)
- ping_service: Check if service is reachable
- check_dependencies: See upstream/downstream dependencies and their health
- inspect_deploy: See deploy history (versions, timestamps)
- query_traces: See distributed trace spans
- check_runbook: Get operational runbook for the service
- diff_config: Compare current vs previous config

Remediation actions (require "service" field):
- restart_service: Restart all pods for a service
- rollback_deploy: Rollback to a specific version (requires "target_version")
- scale_up: Increase replica count (requires "replicas")

Terminal action:
- submit_diagnosis: Submit your diagnosis (supports singular fields or list fields for multi-root tasks)

Root cause categories: oom_crash, db_deadlock, bad_deploy, memory_leak, network_partition, disk_full, config_error, cert_expiry, dns_failure, rate_limit

IMPORTANT: Respond with ONLY a JSON object like:
{"action_type": "read_logs", "service": "auth-service"}
{"action_type": "rollback_deploy", "service": "payment-service", "target_version": "v3.8.1"}
{"action_type": "submit_diagnosis", "root_cause_service": "db-postgres", "root_cause_category": "db_deadlock", "fix_description": "Restarted db-postgres to clear deadlock"}
{"action_type": "submit_diagnosis", "root_cause_services": ["payment-service", "cache-redis"], "root_cause_categories": ["bad_deploy", "memory_leak"], "fix_description": "Rolled back payment-service and restarted cache-redis"}
""")


# ── Helpers ────────────────────────────────────────────────────────────

def format_observation(obs_dict: dict) -> str:
    """Format observation into a readable prompt for the LLM."""
    parts = []

    if obs_dict.get("incident_summary"):
        parts.append(f"INCIDENT SUMMARY: {obs_dict['incident_summary']}")

    parts.append(f"\nSTEP: {obs_dict.get('step_number', 0)}")

    services = obs_dict.get("services", {})
    if services:
        parts.append("\nSERVICE STATUS DASHBOARD:")
        for name, state in services.items():
            status = state.get("status", "UNKNOWN")
            version = state.get("version", "")
            parts.append(f"  {name}: {status} (version: {version})")

    alerts = obs_dict.get("active_alerts", [])
    if alerts:
        parts.append("\nACTIVE ALERTS:")
        for alert in alerts:
            parts.append(f"  {alert}")

    action_result = obs_dict.get("action_result")
    if action_result:
        parts.append(f"\nRESULT OF LAST ACTION:\n{action_result}")

    return "\n".join(parts)


def get_model_message(client: OpenAI, obs_text: str, history: List[str]) -> str:
    """Call the LLM and return the raw response text."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    # Include recent history for context
    for h in history[-6:]:
        messages.append({"role": "user", "content": h})
    messages.append({"role": "user", "content": obs_text})

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=512,
        )
        return response.choices[0].message.content
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return '{"action_type": "read_logs", "service": "auth-service"}'


def parse_action(response_text: str) -> Action:
    """Parse LLM response into an Action object."""
    text = response_text.strip()

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]

    data = json.loads(text)
    return Action(**data)


def _first_unhealthy_service(obs_dict: dict) -> str | None:
    """Return the name of the first non-HEALTHY service, or None if all healthy."""
    for name, state in obs_dict.get("services", {}).items():
        if state.get("status") != "HEALTHY":
            return name
    return None


def incident_fully_resolved(obs_dict: dict) -> bool:
    """Return True when there are no active alerts and all services are HEALTHY."""
    alerts = obs_dict.get("active_alerts", [])
    has_alert = any(str(alert).startswith("[ALERT") for alert in alerts)

    services = obs_dict.get("services", {})
    all_healthy = all(
        state.get("status") == "HEALTHY"
        for state in services.values()
    )

    return (not has_alert) and all_healthy


# ── Main ──────────────────────────────────────────────────────────────

async def run_task(task_id: str) -> float:
    """Run inference on a single task. Returns score in [0, 1]."""
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = IncidentResponseEnv()

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        obs, session_id = env.reset(task_id=task_id)
        obs_dict = obs.model_dump()
        max_steps = env.sessions[session_id].scenario.max_steps

        for step in range(1, max_steps + 1):
            if obs_dict.get("done", False):
                break

            obs_text = format_observation(obs_dict)
            message = get_model_message(client, obs_text, history)

            try:
                action = parse_action(message)
                error = None
            except Exception as e:
                error = str(e)
                parse_penalty = -0.02
                log_step(step=step, action="parse_error", reward=parse_penalty, done=False, error=error)
                rewards.append(parse_penalty)
                steps_taken = step
                history.append(f"Step {step}: parse_error -> reward {parse_penalty:+.2f}")
                continue

            if action.action_type == ActionType.SUBMIT_DIAGNOSIS and not incident_fully_resolved(obs_dict):
                # Redirect to investigating the first unhealthy service instead
                fallback_service = _first_unhealthy_service(obs_dict) or "api-gateway"
                action = Action(
                    action_type=ActionType.CHECK_DEPENDENCIES,
                    service=fallback_service,
                )
                error = "submit_blocked_active_alerts"

            obs, reward, done, info = env.step(session_id, action)
            obs_dict = obs.model_dump()

            reward = reward or 0.0
            rewards.append(reward)
            steps_taken = step

            action_str = action.action_type.value
            if action.service:
                action_str += f"({action.service})"

            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            history.append(f"Step {step}: {action_str} -> reward {reward:+.2f}")

            if done:
                if "grader_result" in info:
                    score = info["grader_result"]["score"]
                break

        # Clamp score to [0, 1]
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


async def main() -> None:
    task_ids = os.getenv("SRE_TASKS", "easy,easy_disk,easy_dns,medium,medium_cert,medium_config,hard,hard_partition_ratelimit,hard_disk_cert").split(",")
    scores = {}

    for task_id in task_ids:
        task_id = task_id.strip()
        score = await run_task(task_id)
        scores[task_id] = score

    print(f"\n{'='*60}", flush=True)
    print("FINAL SCORES:", flush=True)
    for task_id, score in scores.items():
        print(f"  {task_id}: {score:.2f}", flush=True)
    avg = sum(scores.values()) / len(scores) if scores else 0
    print(f"  AVERAGE: {avg:.2f}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
