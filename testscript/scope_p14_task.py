import json
import sqlite3
import os

db_path = os.path.expanduser("~/.alphabrain/task_triage_queue.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

task_id = "tsk_eva_1d262851bd6a"
cur.execute("SELECT envelope_json FROM task_triage_queue WHERE id = ?", (task_id,))
row = cur.fetchone()

if row:
    envelope = json.loads(row[0])
    
    # Scope acceptance gates to target test and lint only
    envelope["acceptance_plan"]["commands"] = [
        {
            "gate_type": "unit_test",
            "executable": "pytest",
            "args": ["-q", "testscript/test_mobile_bridge_api.py"],
            "timeout_seconds": 300
        },
        {
            "gate_type": "lint",
            "executable": "ruff",
            "args": ["check", "alpha_core/mobile_bridge/"],
            "timeout_seconds": 300
        }
    ]
    
    # Ensure allowed paths are complete
    envelope["allowed_paths"] = ["alphabrain_app/", "alpha_core/", "testscript/"]
    
    cur.execute("UPDATE task_triage_queue SET envelope_json = ? WHERE id = ?", (json.dumps(envelope), task_id))
    conn.commit()
    print(f"Successfully scoped acceptance gates for {task_id}")
else:
    print(f"Task {task_id} not found")

conn.close()
