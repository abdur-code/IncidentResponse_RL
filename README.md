# SRE Incident Response Environment

An OpenEnv-compatible reinforcement learning environment that simulates production incident response. AI agents must investigate microservice architectures, diagnose root causes, and apply fixes — just like a real on-call SRE engineer.

## Motivation

Every tech company has on-call rotations, yet there's no standardized benchmark for evaluating AI agents on incident response. This environment fills that gap by simulating realistic production incidents with:

- **Multi-service architectures** with dependency chains and cascading failures
- **Progressive information revelation** — agents must actively investigate (read logs, check metrics, trace requests)
- **Red herrings and misleading symptoms** — alerts point to symptoms, not root causes
- **Concurrent faults** in the hardest tier — testing whether agents can find multiple independent root causes
- **Realistic operational data** — 50+ log lines per service with noise, time-series metrics, distributed traces, deploy history, runbooks, and config diffs

## Service Architecture

All tasks share the same 7-service microservice architecture:

```
                    +--------------+
          +-------->| auth-service |<------+
          |         +------+-------+       |
          |                | depends       | depends
+---------+------+  +------v------+  +-----+--------+
|  api-gateway   |  | cache-redis |  | notification |
|  (entry point) |  +-------------+  |   -service   |
+-+----------+---+                   +--------------+
  |          |
  | depends  | depends
  v          v
+------------+  +-----------------+
|user-service|  |payment-service  |
+-----+------+  +--------+--------+
      | depends          | depends
      v                  v
+----------------------------+
|        db-postgres         |
+----------------------------+
```

Each service has: name, status (`HEALTHY`/`DEGRADED`/`DOWN`), version, replica count, dependencies, logs, metrics, traces, deploy history, config, and runbook data.

## Tasks

Tasks are auto-discovered from the `tasks/` directory. Each task is a self-contained Python file defining a `SCENARIO` object.

| Task ID | Name | Difficulty | Max Steps | Root Cause | Fix Required |
|---------|------|-----------|-----------|------------|--------------|
| `easy` | Single Service OOM Crash | Easy | 15 | `auth-service` (OOM) | `restart_service(auth-service)` |
| `medium` | Cascading Database Deadlock | Medium | 25 | `db-postgres` (deadlock) | `restart_service(db-postgres)` |
| `hard` | Concurrent Faults + Misleading Evidence | Hard | 35 | `payment-service` (bad deploy) AND `cache-redis` (memory leak) | `rollback_deploy(payment-service, v3.8.1)` AND `restart_service(cache-redis)` |

### Task Details

**Easy** — Alert directly names `auth-service` as down. Logs clearly show OOM crash cycle (heap growth, OOM kills, restart exhaustion). Single root cause, single fix.

**Medium** — Alerts blame `payment-service` and `user-service` (both are victims). The real cause is a long-running analytics query deadlocking `db-postgres`. Agent must notice "writes fail but reads work", follow dependency chain to the database, and read `db-postgres` logs to find the deadlock. Red herring: `cache-redis` miss ratio alert (benign TTL expiry).

**Hard** — Two independent faults at the same time: (1) `payment-service` has a bad deploy (v3.8.2, NullPointerException in new validator module), (2) `cache-redis` has a memory leak causing eviction storms that degrade `auth-service`. Red herrings: `user-service` config warnings (benign), `notification-service` queue backup (victim of auth-service). Agent must find and fix BOTH faults. After fixing only one, post-remediation check shows remaining services are still unhealthy.

### Adding New Tasks

To add a new task:

1. Create a new file in `tasks/` (e.g., `tasks/my_new_task.py`)
2. Define a `SCENARIO = IncidentScenario(task_id="my_new_task", ...)` — see existing task files for the template
3. Done. The task loader in `tasks/__init__.py` auto-discovers any `.py` file that exports a `SCENARIO` object.

No changes needed to the environment engine, grader, server, or inference script. The grader is generic — it reads ground truth (root cause services, required fixes, keywords, weights) from the scenario definition.

## Project Structure

```
IncidentResponse_RL/
├── models.py                  # Pydantic models: Action, Observation, State, enums
├── openenv.yaml               # OpenEnv manifest (tasks, models, runtime config)
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container for HF Spaces deployment
├── inference.py               # Baseline agent using OpenAI client
├── README.md
│
├── env/                       # Core environment engine
│   ├── __init__.py
│   ├── scenario.py            # IncidentScenario, ServiceConfig, RequiredFix dataclasses
│   ├── environment.py         # step() / reset() / state() implementation
│   └── services.py            # Alert generation, dependency cascade, data formatting
│
├── tasks/                     # Task definitions (auto-discovered)
│   ├── __init__.py            # Auto-discovery loader → SCENARIOS dict
│   ├── easy_oom.py            # Easy: Single Service OOM Crash
│   ├── medium_deadlock.py     # Medium: Cascading Database Deadlock
│   └── hard_concurrent.py     # Hard: Concurrent Faults + Misleading Evidence
│
├── graders/                   # Scoring engine
│   ├── __init__.py
│   └── grader.py              # Generic rubric-based grader (0.0-1.0)
│
└── server/                    # FastAPI web server
    ├── __init__.py
    └── app.py                 # /reset, /step, /state, /tasks endpoints
```

## Action Space

All actions are sent as a single JSON object with an `action_type` field. Optional fields depend on the action type.

### Investigation Actions (read-only, gather information)

| Action | Required Fields | Returns |
|--------|----------------|---------|
| `read_logs` | `service` | 50+ timestamped log lines with noise and signal |
| `check_metrics` | `service` | Time-series table (CPU, memory, latency, error rate, etc.) |
| `ping_service` | `service` | Reachability check with latency |
| `check_dependencies` | `service` | Upstream dependency list with current health status |
| `inspect_deploy` | `service` | Deploy history (version, timestamp, status) |
| `query_traces` | `service` | Distributed trace spans showing latency breakdown |
| `check_runbook` | `service` | Operational runbook with troubleshooting steps |
| `diff_config` | `service` | Current vs previous config comparison |

### Remediation Actions (modify environment state)

| Action | Required Fields | Effect |
|--------|----------------|--------|
| `restart_service` | `service` | Restarts pods. Fixes OOM/leak issues. No effect if root cause is elsewhere. |
| `rollback_deploy` | `service`, `target_version` | Rolls back to specified version. Must match exact version string. |
| `scale_up` | `service`, `replicas` | Increases replica count. Can alleviate memory pressure. |
| `drain_traffic` | `service` | Stops routing traffic to the service. |

### Terminal Action

| Action | Required Fields | Effect |
|--------|----------------|--------|
| `submit_diagnosis` | `root_cause_service`, `root_cause_category`, `fix_description` | Ends episode, triggers grading. |

### Root Cause Categories

`oom_crash`, `db_deadlock`, `bad_deploy`, `memory_leak`, `network_partition`, `disk_full`, `config_error`, `cert_expiry`, `dns_failure`, `rate_limit`

### Example Actions

```json
{"action_type": "read_logs", "service": "auth-service"}
{"action_type": "check_metrics", "service": "db-postgres"}
{"action_type": "rollback_deploy", "service": "payment-service", "target_version": "v3.8.1"}
{"action_type": "submit_diagnosis", "root_cause_service": "db-postgres", "root_cause_category": "db_deadlock", "fix_description": "Restarted db-postgres to clear deadlock caused by analytics-cron query"}
```

## Observation Space

On `reset()`, the agent receives:
- **Service health dashboard** — all 7 services with status (`HEALTHY`/`DEGRADED`/`DOWN`), version, replica count
- **Active alerts** — severity-tagged alerts (SEV-1/SEV-2/SEV-3)
- **Incident summary** — text description of the situation

On each `step()`, the agent receives:
- **Updated service statuses** — health may change after remediation
- **Updated alerts** — alerts clear when services recover
- **Action result** — the data returned by the action (logs, metrics, traces, etc.)
- **Reward** — per-step reward signal
- **Done flag** — whether the episode has ended
- **Score** — final score (only on terminal step)

### Progressive Revelation

The agent does NOT see all data upfront. It must actively choose which services to investigate and which data to request. Each investigation action consumes a step, creating a planning pressure: the agent must balance information gathering with remediation within the step budget.

### Post-Remediation Feedback

After any remediation action, the observation includes a `[POST-REMEDIATION CHECK]` that lists which services are still unhealthy. This is critical for the hard task — after fixing only one of two faults, the check reveals remaining issues.

## Reward Function

### Per-Step Shaping

| Action | Reward |
|--------|--------|
| Investigating a root-cause service | +0.01 |
| Investigating a non-root-cause service | 0.00 |
| Correct remediation (matches required fix) | +0.05 |
| Wrong remediation (wrong service or wrong fix type) | -0.05 |

### Terminal Grading (0.0 - 1.0)

The grader is generic and rubric-based. Each task defines its own weights:

| Component | Easy | Medium | Hard |
|-----------|------|--------|------|
| Correct root cause service identified | 0.30 | 0.25 | 0.15 |
| Correct root cause category | 0.20 | 0.20 | 0.10 |
| Primary fix applied | 0.30 | 0.25 | 0.15 |
| Secondary fix(es) applied | -- | -- | 0.20 |
| Diagnosis text quality (keyword match) | 0.10 | 0.10 | 0.15 |
| Investigation thoroughness | 0.10 | 0.10 | 0.10 |
| Wrong remediation penalty | -0.03/ea | -0.05/ea | -0.05/ea |

**Diagnosis text scoring** uses deterministic keyword matching — the grader checks if the fix description mentions key terms (service names, fault types, fix actions). No LLM-based judging.

**Investigation thoroughness** checks whether the agent examined at least one root-cause service before submitting.

## Setup

### Local Development

```bash
pip install -r requirements.txt
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t sre-incident-response .
docker run -p 8000:8000 sre-incident-response
```

### API Usage

```bash
# List available tasks
curl http://localhost:8000/tasks

# Reset (start a new episode)
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy"}'

# Step (take an action)
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<SESSION_ID>", "action": {"action_type": "read_logs", "service": "auth-service"}}'

# Get current episode state
curl http://localhost:8000/state/<SESSION_ID>
```

OpenEnv-prefixed endpoints are also available: `/openenv/reset`, `/openenv/step`, `/openenv/state/{session_id}`, `/openenv/tasks`.

### Running Inference

```bash
export HF_TOKEN=your_token
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

python inference.py
```

The inference script runs a baseline LLM agent against all tasks, emitting structured stdout logs:

```
[START] task=easy env=sre_incident_response model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=read_logs(auth-service) reward=0.01 done=false error=null
[STEP] step=2 action=check_metrics(auth-service) reward=0.01 done=false error=null
[STEP] step=3 action=restart_service(auth-service) reward=0.05 done=false error=null
[STEP] step=4 action=submit_diagnosis reward=1.00 done=true error=null
[END] success=true steps=4 score=1.00 rewards=0.01,0.01,0.05,1.00
```

## Baseline Scores

| Task | Expected Score Range | What a Perfect Agent Scores |
|------|---------------------|---------------------------|
| easy | 0.70 - 0.95 | 1.00 |
| medium | 0.40 - 0.75 | 0.90 |
| hard | 0.20 - 0.55 | 0.85 |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | LLM API endpoint | `https://router.huggingface.co/v1` |
| `MODEL_NAME` | Model identifier | `Qwen/Qwen2.5-72B-Instruct` |
| `HF_TOKEN` | HuggingFace API key | Required |
| `PORT` | Server port | `8000` |
| `SRE_TASKS` | Comma-separated task IDs to run in inference | `easy,medium,hard` |

## OpenEnv Spec Compliance

- `openenv.yaml` with metadata, task definitions, typed models, and runtime config
- `step(action)` returns observation, reward, done, info
- `reset()` returns initial observation
- `state()` returns current episode metadata
- Typed Pydantic models for Action, Observation, and State
- 3 tasks with programmatic graders (easy, medium, hard)
- Scores in 0.0-1.0 range with partial progress signals
- Working Dockerfile for containerized execution
- Baseline inference script (`inference.py`) with reproducible scores
