import json
import traceback
from pathlib import Path
from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_core.planning.research_broker import ResearchBroker
from alpha_core.planning.senior_planning_engine import SeniorPlanningEngine
from alpha_protocol.planning import ResearchSnapshot
import alpha_core.planning.senior_planning_engine

# Monkey-patch to intercept and print the raw model response
original_invoke = alpha_core.planning.senior_planning_engine.SeniorPlanningEngine._invoke_agy_planning

def hooked_invoke(self, model, prompt, schema, timeout_seconds=600):
    try:
        res = original_invoke(self, model, prompt, schema, timeout_seconds)
        print(f"\\n--- HOOKED SUCCESSFUL RESPONSE FROM {model} ---\\n", json.dumps(res, indent=2))
        return res
    except Exception as e:
        print(f"\\n--- HOOKED EXCEPTION FROM {model} ---\\n", e)
        raise

alpha_core.planning.senior_planning_engine.SeniorPlanningEngine._invoke_agy_planning = hooked_invoke

def main():
    queue = TaskTriageQueue()
    task_id = "tsk_eva_34dccbae2854"
    snapshot_path = "scratch/task3_research.json"
    
    try:
        snapshot = ResearchSnapshot.model_validate_json(Path(snapshot_path).read_text())
        engine = SeniorPlanningEngine(queue, ResearchBroker())
        print("Executing planning phase with hook...")
        engine.execute_planning_phase(task_id, snapshot)
        print("Success!")
    except Exception as e:
        print("ERROR OCCURRED:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
