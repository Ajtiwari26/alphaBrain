import re
with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    text = f.read()

replacement = """
                if isinstance(name, str):
                    tool_names_set.add(name)
                if isinstance(info, dict):
                    parameters = info.get("parameters")
                    if isinstance(parameters, dict):
                        server = parameters.get("ServerName")
                        tool = parameters.get("ToolName")
                        if isinstance(server, str) and isinstance(tool, str):
                            tool_names_set.add(f"{server}/{tool}")
                            
                # Check for browser tool usage
                is_browser_tool = (
                    isinstance(name, str) and ("chrome-devtools" in name.lower() or "browser" in name.lower())
                )
                if isinstance(info, dict):
                    parameters = info.get("parameters")
                    if isinstance(parameters, dict):
                        server = str(parameters.get("ServerName") or "")
                        if "chrome-devtools" in server.lower() or "browser" in server.lower():
                            is_browser_tool = True
                if is_browser_tool:
                    policy_violations.append(f"Forbidden browser tool usage detected")
"""

text = text.replace(
    """                if isinstance(name, str):
                    tool_names_set.add(name)
                if isinstance(info, dict):
                    parameters = info.get("parameters")
                    if isinstance(parameters, dict):
                        server = parameters.get("ServerName")
                        tool = parameters.get("ToolName")
                        if isinstance(server, str) and isinstance(tool, str):
                            tool_names_set.add(f"{server}/{tool}")""",
    replacement
)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(text)
