import plistlib
import subprocess
from pathlib import Path

PLIST_PATH = Path.home() / "Library/LaunchAgents/com.deploymate.alphabrain.worker.plist"
data = plistlib.loads(PLIST_PATH.read_bytes())
if "EnvironmentVariables" in data:
    del data["EnvironmentVariables"]
PLIST_PATH.write_bytes(plistlib.dumps(data))
subprocess.run(["launchctl", "unload", str(PLIST_PATH)])
subprocess.run(["launchctl", "load", str(PLIST_PATH)])
