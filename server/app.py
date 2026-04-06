"""
FastAPI server for the SRE Incident Response OpenEnv environment.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from models import Action, Observation, State
from env.environment import IncidentResponseEnv
from tasks import SCENARIOS

app = FastAPI(
    title="SRE Incident Response Environment",
    description="An OpenEnv environment for training AI agents on production incident response.",
    version="1.0.0",
)

env = IncidentResponseEnv()


# ── Request/Response models ────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: str = "easy"
    seed: int = 0


class ResetResponse(BaseModel):
    observation: Observation
    session_id: str


class StepRequest(BaseModel):
    session_id: str
    action: Action


class StepResponse(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: Dict


class TaskInfo(BaseModel):
    task_id: str
    name: str
    difficulty: str
    max_steps: int
    description: str


# ── Endpoints ──────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "SRE Incident Response Environment",
        "version": "1.0.0",
        "endpoints": ["/reset", "/step", "/state/{session_id}", "/tasks"],
    }


@app.post("/reset", response_model=ResetResponse)
def reset(request: ResetRequest):
    try:
        obs, session_id = env.reset(task_id=request.task_id, seed=request.seed)
        return ResetResponse(observation=obs, session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/step", response_model=StepResponse)
def step(request: StepRequest):
    try:
        obs, reward, done, info = env.step(request.session_id, request.action)
        # Ensure info is JSON-serializable
        clean_info = {}
        for k, v in info.items():
            clean_info[k] = v
        return StepResponse(observation=obs, reward=reward, done=done, info=clean_info)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/state/{session_id}", response_model=State)
def state(session_id: str):
    try:
        return env.state(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/tasks", response_model=List[TaskInfo])
def tasks():
    result = []
    for tid, scenario in SCENARIOS.items():
        result.append(TaskInfo(
            task_id=tid,
            name=scenario.name,
            difficulty=scenario.difficulty,
            max_steps=scenario.max_steps,
            description=scenario.incident_summary,
        ))
    return result


# ── OpenEnv-prefixed aliases ───────────────────────────────────────────

@app.post("/openenv/reset", response_model=ResetResponse)
def openenv_reset(request: ResetRequest):
    return reset(request)


@app.post("/openenv/step", response_model=StepResponse)
def openenv_step(request: StepRequest):
    return step(request)


@app.get("/openenv/state/{session_id}", response_model=State)
def openenv_state(session_id: str):
    return state(session_id)


@app.get("/openenv/tasks", response_model=List[TaskInfo])
def openenv_tasks():
    return tasks()


# ── Main ───────────────────────────────────────────────────────────────

def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
