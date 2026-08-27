with open("alpha_worker/adapters/antigravity_live.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_event_processing = False

for line in lines:
    if "tool_names_set: set[str] = set()" in line:
        new_lines.append(line)
        new_lines.append("    policy_violations: list[str] = []\n")
        continue

    if 'if isinstance(server, str) and isinstance(tool, str):' in line:
        new_lines.append(line)
        continue

    if 'tool_names_set.add(f"{server}/{tool}")' in line:
        new_lines.append(line)
        new_lines.append("""                if name == "run_command" and isinstance(info, dict):
                    parameters = info.get("parameters")
                    if isinstance(parameters, dict):
                        cmdline = str(parameters.get("CommandLine", "")).lower()
                        for pattern in ["npm install", "npm ci", "npx playwright install", "curl", "wget"]:
                            if pattern in cmdline:
                                policy_violations.append(f"Forbidden command execution detected: {pattern}")
""")
        continue

    if '# 5. Result event status check' in line:
        new_lines.append("""    # 4b. Command policy check
    if policy_violations:
        error_msg = policy_violations[0]
        return AntigravityAttemptOutcome(
            conversation_id=parsed_conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=AGYAttemptStatus.BLOCKED,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=(error_msg,),
            tool_names=tools_tuple,
            final_message=response,
            transcript_path=transcript_path,
            blocked_reason=error_msg,
        )

""")
        new_lines.append(line)
        continue
        
    new_lines.append(line)

with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.writelines(new_lines)
