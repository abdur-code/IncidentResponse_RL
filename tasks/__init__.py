"""
Task auto-discovery and registry.

Any .py file in this directory that defines a module-level SCENARIO variable
(an IncidentScenario instance) will be automatically loaded and registered.

To add a new task:
  1. Create a new .py file in this directory (e.g., tasks/my_new_task.py)
  2. Define SCENARIO = IncidentScenario(task_id="my_new_task", ...)
  3. That's it — the task will be available via the API automatically.
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict

from env.scenario import IncidentScenario


def _discover_scenarios() -> Dict[str, IncidentScenario]:
    """Scan all .py files in tasks/ and collect SCENARIO instances."""
    scenarios: Dict[str, IncidentScenario] = {}
    package_dir = Path(__file__).parent

    for finder, module_name, is_pkg in pkgutil.iter_modules([str(package_dir)]):
        if module_name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"tasks.{module_name}")
            scenario = getattr(module, "SCENARIO", None)
            if isinstance(scenario, IncidentScenario):
                scenarios[scenario.task_id] = scenario
        except Exception as e:
            print(f"Warning: failed to load task module 'tasks.{module_name}': {e}")

    return scenarios


SCENARIOS: Dict[str, IncidentScenario] = _discover_scenarios()
