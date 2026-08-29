import os
import runpy
import sys
import traceback

os.environ["PYTHONUNBUFFERED"] = "1"
sys.argv = ["checkpoint_recovery_harness.py", "--run"]

try:
    runpy.run_path("testscript/checkpoint_recovery_harness.py", run_name="__main__")
except BaseException:
    traceback.print_exc()
